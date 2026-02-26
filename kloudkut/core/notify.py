"""Notifications — Slack webhook and SES email."""
import json
import logging
import ssl
import requests
from kloudkut.core.scanner import Finding

logger = logging.getLogger(__name__)


def _slack(webhook_url: str, findings: list[Finding]) -> None:
    if not webhook_url.startswith("https://"):
        raise ValueError("Slack webhook URL must use HTTPS")
    total = sum(f.monthly_cost for f in findings)
    top = findings[:5]
    lines = [f"• *{f.service}* `{f.resource_name}` — ${f.monthly_cost:,.2f}/mo ({f.reason})" for f in top]
    payload = {
        "text": f":money_with_wings: *KloudKut* found *{len(findings)} idle resources* — potential savings *${total:,.2f}/mo*",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn",
             "text": f":money_with_wings: *KloudKut Scan Complete*\n*{len(findings)} idle resources* | *${total:,.2f}/mo* | *${total*12:,.2f}/yr*"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "Top findings:\n" + "\n".join(lines)}},
        ]
    }
    requests.post(webhook_url, json=payload, timeout=10)


def _email(from_addr: str, to_addr: str, ses_region: str, findings: list[Finding]) -> None:
    import boto3
    total = sum(f.monthly_cost for f in findings)
    rows = "".join(
        f"<tr><td>{f.service}</td><td>{f.resource_name}</td><td>{f.region}</td>"
        f"<td>{f.reason}</td><td>${f.monthly_cost:,.2f}</td></tr>"
        for f in findings[:20]
    )
    body = f"""<h2>KloudKut Scan Results</h2>
<p><b>{len(findings)} idle resources</b> found — potential savings <b>${total:,.2f}/mo</b></p>
<table border="1" cellpadding="6" style="border-collapse:collapse">
<tr><th>Service</th><th>Resource</th><th>Region</th><th>Reason</th><th>Monthly Cost</th></tr>
{rows}
</table>"""
    boto3.client("ses", region_name=ses_region).send_email(
        Source=from_addr,
        Destination={"ToAddresses": [a.strip() for a in to_addr.split(",")]},
        Message={
            "Subject": {"Data": f"KloudKut: {len(findings)} idle resources (${total:,.2f}/mo)"},
            "Body": {"Html": {"Data": body}},
        }
    )


def notify(config: dict, findings: list[Finding]) -> None:
    if not findings:
        return
    notif = config.get("notifications", {})

    slack_url = notif.get("slack", {}).get("webhook_url", "")
    if slack_url:
        try:
            _slack(slack_url, findings)
            logger.info("Slack notification sent")
        except Exception as e:
            logger.warning("Slack notification failed: %s", e)

    email_cfg = notif.get("email", {})
    if email_cfg.get("from_address") and email_cfg.get("to_address"):
        try:
            _email(email_cfg["from_address"], email_cfg["to_address"],
                   email_cfg.get("ses_region", "us-east-1"), findings)
            logger.info("Email notification sent")
        except Exception as e:
            logger.warning("Email notification failed: %s", e)
