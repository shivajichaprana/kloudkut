"""Storage scanners: S3, EBS, EFS, FSx, Backup, ECR."""
import logging
from datetime import datetime, timedelta, UTC
from botocore.exceptions import ClientError
from kloudkut.core import BaseScanner, Finding, get_client, get_sum

logger = logging.getLogger(__name__)


class S3Scanner(BaseScanner):
    service = "S3"

    def scan_region(self, region):
        findings = []
        s3 = get_client("s3", region)
        days = self.config.get("days_since_last_modified", 90)
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # list_buckets is global — call once on us-east-1 to avoid N redundant calls
        try:
            buckets = get_client("s3", "us-east-1").list_buckets().get("Buckets", [])
        except ClientError as e:
            logger.debug("S3 list_buckets failed: %s", e)
            return []

        for bucket in buckets:
            name = bucket["Name"]
            try:
                loc = s3.get_bucket_location(Bucket=name).get("LocationConstraint") or "us-east-1"
                if loc != region:
                    continue
                resp = s3.list_objects_v2(Bucket=name, MaxKeys=1)
                if resp["KeyCount"] == 0:
                    findings.append(Finding(name, name, "S3", region, "Empty bucket", 1.0,
                                            remediation=f"aws s3 rb s3://{name} --force"))
                elif resp["Contents"][0]["LastModified"] < cutoff:
                    findings.append(Finding(name, name, "S3", region, f"No activity in {days}d", 5.0,
                                            remediation=f"aws s3 rb s3://{name} --force"))
            except ClientError as e:
                logger.debug("S3 bucket %s skipped: %s", name, e)
        return findings


class EBSScanner(BaseScanner):
    service = "EBS"

    def scan_region(self, region):
        findings = []
        ec2 = get_client("ec2", region)
        for page in ec2.get_paginator("describe_volumes").paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
            for vol in page.get("Volumes", []):
                name = next((t["Value"] for t in vol.get("Tags", []) if t["Key"] == "Name"), vol["VolumeId"])
                findings.append(Finding(vol["VolumeId"], name, "EBS", region, "Unattached volume",
                                        round(vol["Size"] * 0.10, 2),
                                        remediation=f"aws ec2 delete-volume --volume-id {vol['VolumeId']} --region {region}"))
        return findings


class EFSScanner(BaseScanner):
    service = "EFS"

    def scan_region(self, region):
        findings = []
        efs = get_client("efs", region)
        for page in efs.get_paginator("describe_file_systems").paginate():
            for fs in page.get("FileSystems", []):
                fsid = fs["FileSystemId"]
                size_gb = fs["SizeInBytes"]["Value"] / (1024 ** 3)
                read = get_sum(region, "AWS/EFS", "DataReadIOBytes", "FileSystemId", fsid, self.cw_days, self.cw_period)
                write = get_sum(region, "AWS/EFS", "DataWriteIOBytes", "FileSystemId", fsid, self.cw_days, self.cw_period)
                if read == 0 and write == 0:
                    findings.append(Finding(fsid, fsid, "EFS", region, "No I/O activity", round(size_gb * 0.30, 2)))
        return findings


class FSxScanner(BaseScanner):
    service = "FSX"

    def scan_region(self, region):
        findings = []
        fsx = get_client("fsx", region)
        for page in fsx.get_paginator("describe_file_systems").paginate():
            for fs in page.get("FileSystems", []):
                fsid = fs["FileSystemId"]
                read = get_sum(region, "AWS/FSx", "DataReadBytes", "FileSystemId", fsid, self.cw_days, self.cw_period)
                write = get_sum(region, "AWS/FSx", "DataWriteBytes", "FileSystemId", fsid, self.cw_days, self.cw_period)
                if read == 0 and write == 0:
                    findings.append(Finding(fsid, fsid, f"FSx-{fs['FileSystemType']}", region, "No I/O",
                                            round(fs["StorageCapacity"] * 0.15, 2)))
        return findings


class BackupScanner(BaseScanner):
    service = "BACKUP"

    def scan_region(self, region):
        findings = []
        backup = get_client("backup", region)
        days = self.config.get("days_old", 90)
        cutoff = datetime.now(UTC) - timedelta(days=days)

        for vpage in backup.get_paginator("list_backup_vaults").paginate():
            for vault in vpage.get("BackupVaultList", []):
                name = vault["BackupVaultName"]
                old_count = 0
                for rpage in backup.get_paginator("list_recovery_points_by_backup_vault").paginate(BackupVaultName=name):
                    old_count += sum(1 for p in rpage.get("RecoveryPoints", []) if p["CreationDate"] < cutoff)
                if old_count:
                    findings.append(Finding(name, name, "Backup", region, f"{old_count} old backups",
                                            round(old_count * 5.0, 2)))
        return findings


class ECRScanner(BaseScanner):
    service = "ECR"

    def scan_region(self, region):
        findings = []
        ecr = get_client("ecr", region)
        days = self.config.get("days_old", 180)
        cutoff = datetime.now(UTC) - timedelta(days=days)

        for page in ecr.get_paginator("describe_repositories").paginate():
            for repo in page.get("repositories", []):
                name = repo["repositoryName"]
                old = []
                for ip in ecr.get_paginator("describe_images").paginate(repositoryName=name):
                    old.extend(i for i in ip.get("imageDetails", []) if i.get("imagePushedAt", cutoff) < cutoff)
                if old:
                    findings.append(Finding(name, name, "ECR", region, f"{len(old)} old images",
                                            round(len(old) * 0.1, 2)))
        return findings
