"""Security scanners: GuardDuty, WAF, KMS, Secrets Manager, Macie, Security Hub."""
import logging
from datetime import datetime, timedelta, UTC
from botocore.exceptions import ClientError
from kloudkut.core import BaseScanner, Finding, get_client, get_sum

logger = logging.getLogger(__name__)


class GuardDutyScanner(BaseScanner):
    service = "GUARDDUTY"

    def is_enabled(self, region):
        try:
            gd = get_client("guardduty", region)
            return bool(gd.list_detectors().get("DetectorIds"))
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("AccessDeniedException", "UnauthorizedAccess"):
                return True  # permission issue, not "not activated"
            return False

    def scan_region(self, region):
        findings = []
        gd = get_client("guardduty", region)
        return [Finding(did, did, "GuardDuty", region, "Disabled detector", 4.5)
                for did in gd.list_detectors().get("DetectorIds", [])
                if gd.get_detector(DetectorId=did)["Status"] == "DISABLED"]


class WAFScanner(BaseScanner):
    service = "WAF"

    def scan_region(self, region):
        waf = get_client("wafv2", region)
        return [Finding(acl["Id"], acl["Name"], "WAF", region, "No traffic", 5.0)
                for acl in waf.list_web_acls(Scope="REGIONAL").get("WebACLs", [])
                if get_sum(region, "AWS/WAFV2", "AllowedRequests", "WebACL", acl["Name"], self.cw_days, self.cw_period) +
                   get_sum(region, "AWS/WAFV2", "BlockedRequests", "WebACL", acl["Name"], self.cw_days, self.cw_period) == 0]


class KMSScanner(BaseScanner):
    service = "KMS"

    def scan_region(self, region):
        findings = []
        kms = get_client("kms", region)
        for page in kms.get_paginator("list_keys").paginate():
            for key in page.get("Keys", []):
                try:
                    meta = kms.describe_key(KeyId=key["KeyId"])["KeyMetadata"]
                    if meta["KeyManager"] == "CUSTOMER" and meta["KeyState"] == "Disabled":
                        findings.append(Finding(key["KeyId"], key["KeyId"], "KMS", region, "Disabled key", 1.0))
                except ClientError as e:
                    logger.debug("KMS key %s skipped: %s", key["KeyId"], e)
        return findings


class SecretsManagerScanner(BaseScanner):
    service = "SECRETSMANAGER"

    def scan_region(self, region):
        findings = []
        sm = get_client("secretsmanager", region)
        days = self.config.get("days", 90)
        cutoff = datetime.now(UTC) - timedelta(days=days)
        for page in sm.get_paginator("list_secrets").paginate():
            for secret in page.get("SecretList", []):
                last = secret.get("LastAccessedDate")
                if not last or last < cutoff:
                    findings.append(Finding(secret["Name"], secret["Name"], "Secrets Manager", region,
                                            f"Not accessed in {days}d", 0.4))
        return findings


class MacieScanner(BaseScanner):
    service = "MACIE"

    def is_enabled(self, region):
        try:
            status = get_client("macie2", region).get_macie_session().get("status")
            return status is not None  # any status means it's been activated
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("AccessDeniedException",):
                return True  # permission issue, not "not activated"
            # "Macie is not enabled" → AccessDeniedException or similar
            return False

    def scan_region(self, region):
        findings = []
        try:
            if get_client("macie2", region).get_macie_session().get("status") == "PAUSED":
                findings.append(Finding("macie", "Macie", "Macie", region, "Paused session", 5.0))
        except ClientError as e:
            logger.debug("Macie not enabled in %s: %s", region, e)
        return findings


class SecurityHubScanner(BaseScanner):
    service = "SECURITYHUB"

    def is_enabled(self, region):
        try:
            get_client("securityhub", region).describe_hub()
            return True
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("AccessDeniedException",):
                return True
            # InvalidAccessException = "not subscribed to Security Hub"
            return False

    def scan_region(self, region):
        findings = []
        try:
            sh = get_client("securityhub", region)
            sh.describe_hub()
            findings = [Finding(std["StandardsSubscriptionArn"],
                                std["StandardsArn"].split("/")[-1],
                                "Security Hub", region, "Suspended standard", 2.0)
                        for std in sh.get_enabled_standards().get("StandardsSubscriptions", [])
                        if std["StandardsStatus"] == "SUSPENDED"]
        except ClientError as e:
            logger.debug("SecurityHub not enabled in %s: %s", region, e)
        return findings
