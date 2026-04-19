#!/usr/bin/env python3
"""KloudKut — AWS Cost Optimization Tool."""
import argparse
import json
import os
import sys
import time
import logging
from pathlib import Path
from colorama import init, Fore

try:
    from kloudkut import __version__
    from kloudkut.core import load_config, notify, save_scan, get_delta
    from kloudkut.core.aws import get_regions, get_client, get_client_for_session, set_profile, close_all_clients
    from kloudkut.core.scanner import _cache_clear
    from kloudkut.scanners import ALL_SCANNERS, SCANNER_MAP
    from kloudkut.reports import generate_json, generate_csv, generate_html
except ImportError as e:
    print(f"Error: {e}\nInstall dependencies: pip install -r requirements.txt")
    sys.exit(1)

_PARTIAL_FILE = ".kloudkut_partial.json"


def _init_color(no_color: bool) -> None:
    if no_color or os.getenv("NO_COLOR") or not sys.stdout.isatty():
        init(autoreset=True, strip=True, convert=False)
        for attr in ["RED", "GREEN", "YELLOW", "CYAN", "BLUE", "MAGENTA", "WHITE", "RESET"]:
            setattr(Fore, attr, "")
    else:
        init(autoreset=True)


def banner(quiet: bool) -> None:
    if quiet:
        return
    print(f"\n{Fore.CYAN}{'━'*55}")
    print(f"  🎯 KloudKut v{__version__} — AWS Cost Optimization")
    print(f"{'━'*55}\n")


def print_summary(findings, elapsed: float, quiet: bool) -> None:
    total = round(sum(f.monthly_cost for f in findings), 2)
    services = len({f.service for f in findings})
    delta = get_delta()
    if quiet:
        print(f"findings={len(findings)} monthly=${total:.2f} annual=${total*12:.2f}")
        return
    print(f"\n{Fore.GREEN}{'━'*55}")
    print(f"  SCAN COMPLETE  ({elapsed:.1f}s)")
    print(f"{'━'*55}")
    print(f"  {Fore.YELLOW}Idle Resources:  {len(findings)}")
    print(f"  Services Hit:    {services}")
    print(f"  Monthly Savings: ${total:,.2f}")
    print(f"  Annual Savings:  ${total*12:,.2f}")
    if delta:
        sign = "+" if delta["delta"] >= 0 else ""
        color = Fore.RED if delta["delta"] > 0 else Fore.GREEN
        print(f"  {color}vs Last Scan:    {sign}${delta['delta']:,.2f}/mo")
    print(f"{'━'*55}\n")


def _save_partial(findings) -> None:
    from dataclasses import asdict
    with open(_PARTIAL_FILE, "w") as f:
        json.dump([asdict(x) for x in findings], f)


def _load_partial() -> list:
    from kloudkut.core.scanner import Finding
    if not os.path.exists(_PARTIAL_FILE):
        return []
    try:
        with open(_PARTIAL_FILE) as f:
            return [Finding(**r) for r in json.load(f)]
    except Exception:
        return []


def _safe_output_path(path: str) -> Path:
    if ".." in os.path.normpath(path).split(os.sep):
        raise ValueError(f"Path traversal detected: {path}")
    return Path(path).resolve()


def _generate_sarif(findings, path: str) -> None:
    results = [{"ruleId": f.service, "level": "warning",
                "message": {"text": f"{f.reason} — ${f.monthly_cost:,.2f}/mo"},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": f"aws://{f.region}/{f.resource_id}"}}}]}
               for f in findings]
    sarif = {"version": "2.1.0", "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
             "runs": [{"tool": {"driver": {"name": "KloudKut", "version": __version__,
                                           "informationUri": "https://github.com/shivajichaprana/kloudkut",
                                           "rules": [{"id": s.service, "name": s.service,
                                                      "shortDescription": {"text": f"Idle {s.service} resource"}}
                                                     for s in ALL_SCANNERS]}},
                       "results": results}]}
    _safe_output_path(path).write_text(json.dumps(sarif, indent=2))


def _generate_junit(findings, path: str) -> None:
    from xml.sax.saxutils import escape, quoteattr

    cases = "\n".join(
        f'  <testcase classname={quoteattr(f.service)} name={quoteattr(f.resource_name)} time="0">'
        f'<failure message={quoteattr(f.reason)}>${f.monthly_cost:,.2f}/mo in {escape(f.region)}</failure></testcase>'
        for f in findings
    )
    xml = (f'<?xml version="1.0"?>\n'
           f'<testsuite name="KloudKut" tests="{len(findings)}" failures="{len(findings)}" '
           f'errors="0" time="0">\n{cases}\n</testsuite>')
    _safe_output_path(path).write_text(xml)


def _check_service_availability(scanner, regions):
    """Check if a service is enabled in at least one region.

    Returns (is_available, skipped_regions) where skipped_regions is the list
    of regions where the service is not activated.
    """
    skipped_regions = []
    available_regions = []
    for region in regions:
        try:
            if scanner.is_enabled(region):
                available_regions.append(region)
            else:
                skipped_regions.append(region)
        except Exception:
            # If the check itself fails, assume it's available (scan will
            # handle the error gracefully via _safe_scan).
            available_regions.append(region)
    return available_regions, skipped_regions


def _run_scanners(scanners, config, regions, no_cache, session=None, label=""):
    """Run scanners, optionally injecting a specific boto3 session for multi-account."""
    import kloudkut.core.aws as aws_module
    from tqdm import tqdm
    from kloudkut.scanners.network import CloudFrontScanner, Route53Scanner

    # Reset global-service dedup flags so each _run_scanners call starts fresh
    CloudFrontScanner._scanned = False
    Route53Scanner._scanned = False

    findings = []
    skipped_services = {}  # {service_name: [skipped_regions]}

    with tqdm(scanners, desc=f"Scanning {label}".strip(), unit="svc", colour="cyan") as bar:
        for scanner_cls in bar:
            bar.set_description(f"Checking {scanner_cls.service:<20}")

            if session:
                orig = aws_module.get_client
                aws_module.get_client = lambda svc, reg: _make_session_client(session, svc, reg)
                try:
                    scanner = scanner_cls(config, regions)
                    available_regions, skipped_regions = _check_service_availability(scanner, regions)
                    if skipped_regions:
                        skipped_services[scanner_cls.service] = skipped_regions
                    if not available_regions:
                        continue
                    scanner.regions = available_regions
                    bar.set_description(f"Scanning {scanner_cls.service:<20}")
                    findings.extend(scanner.scan(use_cache=False))
                    close_all_clients()  # free FDs between service scans
                finally:
                    aws_module.get_client = orig
            else:
                scanner = scanner_cls(config, regions)
                available_regions, skipped_regions = _check_service_availability(scanner, regions)
                if skipped_regions:
                    skipped_services[scanner_cls.service] = skipped_regions
                if not available_regions:
                    continue
                scanner.regions = available_regions
                bar.set_description(f"Scanning {scanner_cls.service:<20}")
                findings.extend(scanner.scan(use_cache=not no_cache))
                close_all_clients()  # free FDs between service scans

    return findings, skipped_services


def _make_session_client(session, svc, reg):
    return get_client_for_session(session, svc, reg)


class _NullCtx:
    def __init__(self, it): self._it = it
    def __enter__(self): return self._it
    def __exit__(self, *_): pass


def main():
    parser = argparse.ArgumentParser(prog="kloudkut", description="AWS Cost Optimization")
    parser.add_argument("--version", action="version", version=f"kloudkut {__version__}")
    parser.add_argument("--services", nargs="+", metavar="SVC")
    parser.add_argument("--regions", nargs="+", metavar="REGION")
    parser.add_argument("--accounts", nargs="+", metavar="ACCOUNT_ID",
                        help="AWS account IDs to scan via STS AssumeRole")
    parser.add_argument("--role-name", metavar="ROLE", default="KloudKutReadOnly")
    parser.add_argument("--profile", metavar="PROFILE", help="AWS named profile")
    parser.add_argument("--config", metavar="FILE", help="Path to config YAML (default: config/config.yaml)")
    parser.add_argument("--exclude-tag", nargs="+", metavar="KEY=VALUE")
    parser.add_argument("--min-cost", type=float, default=0.0, metavar="N")
    parser.add_argument("--since", metavar="YYYY-MM-DD", help="Only show findings for resources active since date")
    parser.add_argument("--output-dir", metavar="DIR", default=".", help="Directory for all report outputs")
    parser.add_argument("--json", metavar="FILE", help="Export findings to JSON")
    parser.add_argument("--html", metavar="FILE", help="Export HTML report")
    parser.add_argument("--csv", action="store_true")
    parser.add_argument("--format", choices=["sarif", "junit"], metavar="FMT")
    parser.add_argument("--format-output", metavar="FILE")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--clear-cache", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--fail-on-findings", action="store_true")
    parser.add_argument("--remediate", action="store_true",
                        help="Execute remediation commands for findings (use with --dry-run to preview)")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    _init_color(args.no_color or args.quiet)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s"
    )

    if args.clear_cache:
        _cache_clear()
        if os.path.exists(_PARTIAL_FILE):
            os.remove(_PARTIAL_FILE)
        if not args.quiet:
            print(f"{Fore.GREEN}✓ Cache cleared")
        return

    banner(args.quiet)

    import boto3
    try:
        session = boto3.Session(profile_name=args.profile) if args.profile else boto3.Session()
        if session.get_credentials() is None:
            raise RuntimeError("No credentials")
    except Exception:
        print(f"{Fore.RED}✗ AWS credentials not found")
        print(f"{Fore.YELLOW}Configure: aws configure  OR  set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY")
        sys.exit(1)

    # Propagate profile to the client factory so all scanners use it
    set_profile(args.profile)

    # Grab account ID for report headers
    try:
        account_id = session.client("sts").get_caller_identity()["Account"]
    except Exception:
        account_id = "unknown"

    exclude_tags = {}
    for tag in (args.exclude_tag or []):
        if "=" in tag:
            k, v = tag.split("=", 1)
            exclude_tags[k] = v

    from kloudkut.core.config import load_config as _load_config
    _load_config.cache_clear()

    # Support --config for custom config file path
    if args.config:
        import os as _os
        _os.environ["KLOUDKUT_CONFIG"] = args.config

    config = _load_config()

    if exclude_tags:
        for svc in config:
            if isinstance(config[svc], dict):
                config[svc].setdefault("exclude_tags", exclude_tags)

    regions = args.regions or get_regions()

    if args.services:
        scanners = [SCANNER_MAP[s.upper()] for s in args.services if s.upper() in SCANNER_MAP]
        missing = [s for s in args.services if s.upper() not in SCANNER_MAP]
        if missing and not args.quiet:
            print(f"{Fore.YELLOW}⚠ Unknown services: {', '.join(missing)}")
    else:
        scanners = ALL_SCANNERS

    if args.dry_run:
        if not args.quiet:
            print(f"{Fore.YELLOW}DRY RUN — would scan:")
            for s in scanners:
                print(f"  • {s.service}")
            print(f"\n  {len(scanners)} services × {len(regions)} regions")
            if exclude_tags:
                print(f"  Excluding tags: {exclude_tags}")
            if args.min_cost > 0:
                print(f"  Min cost filter: ${args.min_cost}/mo")
            if args.accounts:
                print(f"  Accounts: {', '.join(args.accounts)}")
        return

    # Resolve output directory
    out_dir = os.path.realpath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    start = time.time()
    all_findings = _load_partial()
    scanned_services = {f.service for f in all_findings}

    # Build account list — default session or assumed-role sessions
    accounts_to_scan = []
    if args.accounts:
        sts = session.client("sts")
        for account_id in args.accounts:
            try:
                role_arn = f"arn:aws:iam::{account_id}:role/{args.role_name}"
                creds = sts.assume_role(RoleArn=role_arn, RoleSessionName="KloudKut")["Credentials"]
                acct_session = boto3.Session(
                    aws_access_key_id=creds["AccessKeyId"],
                    aws_secret_access_key=creds["SecretAccessKey"],
                    aws_session_token=creds["SessionToken"],
                )
                accounts_to_scan.append((account_id, acct_session))
            except Exception as e:
                print(f"{Fore.YELLOW}⚠ Could not assume role in {account_id}: {e}")
    else:
        accounts_to_scan = [("default", None)]  # None = use default lru_cache clients

    all_skipped = {}  # {service: [regions]} across all accounts
    try:
        for account_id, acct_session in accounts_to_scan:
            label = f"[{account_id}]" if len(accounts_to_scan) > 1 else ""
            pending = [s for s in scanners if s.service not in scanned_services or acct_session]
            findings, skipped = _run_scanners(pending, config, regions, args.no_cache, acct_session, label)
            all_findings.extend(findings)
            _save_partial(all_findings)
            for svc, regs in skipped.items():
                all_skipped.setdefault(svc, []).extend(regs)
    except KeyboardInterrupt:
        if not args.quiet:
            print(f"\n{Fore.YELLOW}⚠ Interrupted — partial results saved. Re-run to resume.")
        sys.exit(130)

    if os.path.exists(_PARTIAL_FILE):
        os.remove(_PARTIAL_FILE)

    if args.min_cost > 0:
        all_findings = [f for f in all_findings if f.monthly_cost >= args.min_cost]

    # --since filter: keep findings whose resource_id appears in recent CloudWatch data
    # (approximated by filtering on details.created_at if present, otherwise pass-through)
    if args.since:
        from datetime import datetime, UTC
        try:
            since_dt = datetime.fromisoformat(args.since).replace(tzinfo=UTC)
            all_findings = [f for f in all_findings
                            if not f.details.get("created_at") or
                            datetime.fromisoformat(str(f.details["created_at"])) >= since_dt]
        except ValueError:
            print(f"{Fore.YELLOW}⚠ Invalid --since date format, expected YYYY-MM-DD")

    all_findings.sort(key=lambda f: f.monthly_cost, reverse=True)
    elapsed = time.time() - start

    # Save to history for trend tracking
    save_scan(all_findings)

    print_summary(all_findings, elapsed, args.quiet)

    # Show skipped (not-activated) services
    if all_skipped and not args.quiet:
        print(f"\n{Fore.YELLOW}{'━'*55}")
        print(f"  SKIPPED — Services Not Activated ({len(all_skipped)})")
        print(f"{'━'*55}")
        for svc, regs in sorted(all_skipped.items()):
            unique_regs = sorted(set(regs))
            if len(unique_regs) == len(regions):
                print(f"  {Fore.YELLOW}⊘ {svc:<25} (all regions)")
            else:
                print(f"  {Fore.YELLOW}⊘ {svc:<25} ({', '.join(unique_regs)})")
        print(f"{Fore.YELLOW}{'━'*55}\n")

    def _out(filename):
        return os.path.join(out_dir, filename) if out_dir != "." else filename

    if args.html:
        p = args.html if os.path.isabs(args.html) else _out(args.html)
        html_path = generate_html(all_findings, p, account_id=account_id)
        if not args.quiet:
            print(f"{Fore.GREEN}✓ HTML report: {html_path}")

    if args.csv:
        csv_path = generate_csv(all_findings, _out("reports"))
        if not args.quiet:
            print(f"{Fore.GREEN}✓ CSV report:  {csv_path}")

    if args.json:
        p = args.json if os.path.isabs(args.json) else _out(args.json)
        generate_json(all_findings, p)
        if not args.quiet:
            print(f"{Fore.GREEN}✓ JSON export: {p}")

    if args.format:
        out = args.format_output or _out(f"kloudkut.{args.format}")
        if args.format == "sarif":
            _generate_sarif(all_findings, out)
        else:
            _generate_junit(all_findings, out)
        if not args.quiet:
            print(f"{Fore.GREEN}✓ {args.format.upper()} output: {out}")

    if args.notify:
        notify(config, all_findings)
        if not args.quiet:
            print(f"{Fore.GREEN}✓ Notifications sent")

    if getattr(args, "remediate", False) and all_findings:
        import subprocess
        remediable = [f for f in all_findings if f.remediation]
        if not args.quiet:
            print(f"\n{Fore.YELLOW}⚡ Remediating {len(remediable)} findings...")
        for f in remediable:
            if args.dry_run:
                print(f"  [DRY RUN] {f.remediation}")
            else:
                try:
                    subprocess.run(f.remediation.split(), check=True, capture_output=True)  # noqa: S603
                    if not args.quiet:
                        print(f"  {Fore.GREEN}✓ {f.resource_name}: {f.remediation}")
                except subprocess.CalledProcessError as e:
                    print(f"  {Fore.RED}✗ {f.resource_name}: {e.stderr.decode().strip()}")

    if all_findings and not args.quiet:
        print(f"\n{Fore.CYAN}Top 10 Findings:")
        for f in all_findings[:10]:
            url = f.details.get("console_url", "")
            print(f"  {Fore.RED}${f.monthly_cost:>8,.2f}/mo  "
                  f"{f.service:<20} {f.resource_name:<30} {f.region}  {f.reason}")
            if url:
                print(f"  {Fore.CYAN}  → {url}")
            if f.remediation:
                print(f"  {Fore.YELLOW}  ⚡ {f.remediation}")

    if args.fail_on_findings and all_findings:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
