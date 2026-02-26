"""Tests for KloudKut."""
import pytest
from unittest.mock import patch, MagicMock
from kloudkut.core.scanner import BaseScanner, Finding
from kloudkut.core.config import load_config
from kloudkut.reports import generate_json, generate_csv, generate_html
from kloudkut.scanners import ALL_SCANNERS, SCANNER_MAP
import json, os, tempfile


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_findings():
    return [
        Finding("i-123", "web-server", "EC2", "us-east-1", "CPU 0.5%", 150.0),
        Finding("db-1", "prod-db", "RDS", "us-east-1", "Zero connections", 300.0),
        Finding("bucket-1", "old-data", "S3", "us-east-1", "No activity in 90d", 5.0),
    ]


@pytest.fixture
def mock_scanner():
    class TestScanner(BaseScanner):
        service = "TEST"
        def scan_region(self, region):
            return [Finding("r1", "resource-1", "TEST", region, "idle", 100.0)]
    return TestScanner


# ── Core ──────────────────────────────────────────────────────────────────────

class TestFinding:
    def test_creation(self):
        f = Finding("id", "name", "EC2", "us-east-1", "idle", 100.0)
        assert f.resource_id == "id"
        assert f.monthly_cost == 100.0

    def test_details(self):
        f = Finding("id", "name", "EC2", "us-east-1", "idle", 100.0, {"cpu": 0.5})
        assert f.details["cpu"] == 0.5


class TestBaseScanner:
    def test_parallel_scan(self, mock_scanner):
        scanner = mock_scanner({}, ["us-east-1", "us-west-2"])
        findings = scanner.scan(use_cache=False)
        assert len(findings) == 2

    def test_sorted_by_cost(self, mock_scanner):
        class MultiScanner(BaseScanner):
            service = "MULTI"
            def scan_region(self, region):
                return [
                    Finding("r1", "r1", "MULTI", region, "idle", 50.0),
                    Finding("r2", "r2", "MULTI", region, "idle", 200.0),
                ]
        scanner = MultiScanner({}, ["us-east-1"])
        findings = scanner.scan(use_cache=False)
        assert findings[0].monthly_cost >= findings[1].monthly_cost

    def test_error_isolation(self):
        class FailScanner(BaseScanner):
            service = "FAIL"
            def scan_region(self, region):
                raise RuntimeError("API Error")
        scanner = FailScanner({}, ["us-east-1", "us-west-2"])
        findings = scanner.scan(use_cache=False)
        assert findings == []

    def test_caching(self, mock_scanner):
        scanner = mock_scanner({}, ["us-east-1"])
        f1 = scanner.scan(use_cache=True)
        f2 = scanner.scan(use_cache=True)
        assert f1 == f2


# ── Config ────────────────────────────────────────────────────────────────────

class TestConfig:
    def test_load_returns_dict(self):
        config = load_config()
        assert isinstance(config, dict)

    def test_ec2_config_present(self):
        config = load_config()
        assert "EC2" in config

    def test_ec2_has_cpu_threshold(self):
        config = load_config()
        assert "avgCpu" in config["EC2"]


# ── Scanner Registry ──────────────────────────────────────────────────────────

class TestScannerRegistry:
    def test_all_scanners_have_service(self):
        for scanner in ALL_SCANNERS:
            assert scanner.service, f"{scanner.__name__} missing service attribute"

    def test_scanner_map_complete(self):
        assert len(SCANNER_MAP) == len(ALL_SCANNERS)

    def test_scanner_map_lookup(self):
        assert "EC2" in SCANNER_MAP
        assert "RDS" in SCANNER_MAP
        assert "S3" in SCANNER_MAP

    def test_all_scanners_instantiable(self):
        for scanner_cls in ALL_SCANNERS:
            scanner = scanner_cls({}, [])
            assert hasattr(scanner, "scan")


# ── Reports ───────────────────────────────────────────────────────────────────

class TestReports:
    def test_json_report(self, sample_findings, tmp_path):
        path = str(tmp_path / "report.json")
        generate_json(sample_findings, path)
        with open(path) as f:
            data = json.load(f)
        assert data["total_findings"] == 3
        assert data["total_monthly_savings"] == 455.0

    def test_csv_report(self, sample_findings, tmp_path):
        path = generate_csv(sample_findings, str(tmp_path))
        assert os.path.exists(path)

    def test_html_report(self, sample_findings, tmp_path):
        path = str(tmp_path / "report.html")
        generate_html(sample_findings, path)
        with open(path) as f:
            content = f.read()
        assert "KloudKut" in content
        assert "455" in content

    def test_empty_findings(self, tmp_path):
        path = str(tmp_path / "empty.json")
        generate_json([], path)
        with open(path) as f:
            data = json.load(f)
        assert data["total_findings"] == 0
        assert data["total_monthly_savings"] == 0


# ── Savings Calculation ───────────────────────────────────────────────────────

class TestSavings:
    def test_total_savings(self, sample_findings):
        total = sum(f.monthly_cost for f in sample_findings)
        assert total == 455.0

    def test_annual_savings(self, sample_findings):
        annual = sum(f.monthly_cost for f in sample_findings) * 12
        assert annual == 5460.0

    def test_sort_by_cost(self, sample_findings):
        sorted_findings = sorted(sample_findings, key=lambda f: f.monthly_cost, reverse=True)
        assert sorted_findings[0].monthly_cost == 300.0
        assert sorted_findings[-1].monthly_cost == 5.0


# ── Scanner Behaviour ─────────────────────────────────────────────────────────

class TestScannerBehaviour:
    def test_safe_scan_isolates_errors(self):
        class BurstScanner(BaseScanner):
            service = "BURST"
            calls = 0
            def scan_region(self, region):
                BurstScanner.calls += 1
                if region == "us-east-1":
                    raise RuntimeError("throttled")
                return [Finding("r", "r", "BURST", region, "idle", 10.0)]
        scanner = BurstScanner({}, ["us-east-1", "us-west-2"])
        findings = scanner.scan(use_cache=False)
        assert len(findings) == 1
        assert findings[0].region == "us-west-2"

    def test_findings_sorted_descending(self):
        class CostScanner(BaseScanner):
            service = "COST"
            def scan_region(self, region):
                return [
                    Finding("a", "a", "COST", region, "x", 10.0),
                    Finding("b", "b", "COST", region, "x", 500.0),
                    Finding("c", "c", "COST", region, "x", 50.0),
                ]
        findings = CostScanner({}, ["us-east-1"]).scan(use_cache=False)
        costs = [f.monthly_cost for f in findings]
        assert costs == sorted(costs, reverse=True)

    def test_scanner_uses_service_config(self):
        class CfgScanner(BaseScanner):
            service = "CFGTEST"
            def scan_region(self, region):
                return [Finding("r", "r", "CFGTEST", region, "x", self.config.get("cost", 0))]
        scanner = CfgScanner({"CFGTEST": {"cost": 42.0}}, ["us-east-1"])
        findings = scanner.scan(use_cache=False)
        assert findings[0].monthly_cost == 42.0


# ── Pricing ───────────────────────────────────────────────────────────────────

class TestPricing:
    def test_ec2_known_type(self):
        from kloudkut.core.pricing import ec2_monthly
        assert ec2_monthly("t3.micro") == round(0.0104 * 730, 2)

    def test_ec2_unknown_type_fallback(self):
        from kloudkut.core.pricing import ec2_monthly
        assert ec2_monthly("unknown.type") > 0

    def test_rds_multi_az_doubles_cost(self):
        from kloudkut.core.pricing import rds_monthly
        single = rds_monthly("db.t3.micro", multi_az=False)
        multi = rds_monthly("db.t3.micro", multi_az=True)
        assert multi == single * 2

    def test_elasticache_monthly(self):
        from kloudkut.core.pricing import elasticache_monthly
        assert elasticache_monthly("cache.t3.micro") == round(0.017 * 730, 2)

    def test_nat_monthly(self):
        from kloudkut.core.pricing import nat_monthly
        assert nat_monthly() == round(0.045 * 730, 2)

    def test_eks_monthly(self):
        from kloudkut.core.pricing import eks_monthly
        assert eks_monthly() == round(0.10 * 730, 2)

    def test_sagemaker_monthly(self):
        from kloudkut.core.pricing import sagemaker_monthly
        assert sagemaker_monthly("ml.m5.large") == round(0.134 * 730, 2)

    def test_opensearch_monthly_multi_node(self):
        from kloudkut.core.pricing import opensearch_monthly
        single = opensearch_monthly("m5.large.search", 1)
        triple = opensearch_monthly("m5.large.search", 3)
        assert triple == single * 3

    def test_msk_monthly(self):
        from kloudkut.core.pricing import msk_monthly
        assert msk_monthly("kafka.m5.large", 2) == round(0.216 * 730 * 2, 2)

    def test_redshift_monthly(self):
        from kloudkut.core.pricing import redshift_monthly
        assert redshift_monthly("dc2.large", 2) == round(0.25 * 730 * 2, 2)


# ── Notifications ─────────────────────────────────────────────────────────────

class TestNotify:
    def test_slack_rejects_non_https(self):
        from kloudkut.core.notify import _slack
        with pytest.raises(ValueError, match="HTTPS"):
            _slack("http://hooks.slack.com/test", [])

    def test_notify_skips_empty_findings(self):
        from kloudkut.core.notify import notify
        # Should not raise even with empty config
        notify({}, [])

    def test_notify_skips_missing_webhook(self):
        from kloudkut.core.notify import notify
        config = {"notifications": {"slack": {"webhook_url": ""}}}
        notify(config, [Finding("id", "name", "EC2", "us-east-1", "idle", 100.0)])


# ── Tag Exclusion ─────────────────────────────────────────────────────────────

class TestTagExclusion:
    def test_excluded_returns_true_on_match(self):
        from kloudkut.scanners.compute import _excluded
        tags = [{"Key": "Environment", "Value": "production"}]
        assert _excluded(tags, {"Environment": "production"}) is True

    def test_excluded_returns_false_on_no_match(self):
        from kloudkut.scanners.compute import _excluded
        tags = [{"Key": "Environment", "Value": "staging"}]
        assert _excluded(tags, {"Environment": "production"}) is False

    def test_excluded_empty_tags(self):
        from kloudkut.scanners.compute import _excluded
        assert _excluded([], {"Environment": "production"}) is False

    def test_excluded_empty_exclude_map(self):
        from kloudkut.scanners.compute import _excluded
        tags = [{"Key": "Environment", "Value": "production"}]
        assert _excluded(tags, {}) is False


# ── Min Cost Filter ───────────────────────────────────────────────────────────

class TestMinCostFilter:
    def test_filters_below_threshold(self, sample_findings):
        filtered = [f for f in sample_findings if f.monthly_cost >= 100.0]
        assert all(f.monthly_cost >= 100.0 for f in filtered)
        assert len(filtered) == 2

    def test_zero_threshold_keeps_all(self, sample_findings):
        filtered = [f for f in sample_findings if f.monthly_cost >= 0.0]
        assert len(filtered) == len(sample_findings)


# ── Path Traversal Protection ─────────────────────────────────────────────────

class TestPathTraversal:
    def test_json_blocks_traversal(self, sample_findings):
        from kloudkut.reports import generate_json
        with pytest.raises(ValueError):
            generate_json(sample_findings, "../../etc/passwd")

    def test_html_blocks_traversal(self, sample_findings):
        from kloudkut.reports import generate_html
        with pytest.raises(ValueError):
            generate_html(sample_findings, "../../../tmp/evil.html")

    def test_safe_path_allowed(self, sample_findings, tmp_path):
        from kloudkut.reports import generate_json
        path = str(tmp_path / "safe.json")
        generate_json(sample_findings, path)
        import os
        assert os.path.exists(path)


# ── Cache Key Config Hash ─────────────────────────────────────────────────────

class TestCacheKeyConfigHash:
    def test_different_config_different_key(self):
        class S1(BaseScanner):
            service = "HASHTEST"
            def scan_region(self, r): return []

        s1 = S1({"HASHTEST": {"avgCpu": 5}}, ["us-east-1"])
        s2 = S1({"HASHTEST": {"avgCpu": 10}}, ["us-east-1"])
        assert s1._config_hash != s2._config_hash

    def test_same_config_same_key(self):
        class S2(BaseScanner):
            service = "HASHTEST2"
            def scan_region(self, r): return []

        s1 = S2({"HASHTEST2": {"avgCpu": 5}}, ["us-east-1"])
        s2 = S2({"HASHTEST2": {"avgCpu": 5}}, ["us-east-1"])
        assert s1._config_hash == s2._config_hash


# ── Scanner Unit Tests (mocked boto3) ────────────────────────────────────────

class TestEC2Scanner:
    def test_stopped_instance_flagged(self):
        from kloudkut.scanners.compute import EC2Scanner
        mock_ec2 = MagicMock()
        mock_ec2.get_paginator.return_value.paginate.return_value = [{
            "Reservations": [{"Instances": [{
                "InstanceId": "i-123", "InstanceType": "t3.micro",
                "State": {"Name": "stopped"}, "Tags": []
            }]}]
        }]
        with patch("kloudkut.scanners.compute.get_client", return_value=mock_ec2), \
             patch("kloudkut.scanners.compute.get_avg", return_value=0.0), \
             patch("kloudkut.scanners.compute.get_sum", return_value=0.0):
            findings = EC2Scanner({}, ["us-east-1"]).scan_region("us-east-1")
        assert len(findings) == 1
        assert findings[0].resource_id == "i-123"
        assert findings[0].remediation != ""

    def test_excluded_tag_skipped(self):
        from kloudkut.scanners.compute import EC2Scanner
        mock_ec2 = MagicMock()
        mock_ec2.get_paginator.return_value.paginate.return_value = [{
            "Reservations": [{"Instances": [{
                "InstanceId": "i-456", "InstanceType": "t3.micro",
                "State": {"Name": "stopped"},
                "Tags": [{"Key": "Environment", "Value": "production"}]
            }]}]
        }]
        with patch("kloudkut.scanners.compute.get_client", return_value=mock_ec2):
            findings = EC2Scanner({"EC2": {"exclude_tags": {"Environment": "production"}}},
                                  ["us-east-1"]).scan_region("us-east-1")
        assert findings == []

    def test_idle_running_instance_flagged(self):
        from kloudkut.scanners.compute import EC2Scanner
        mock_ec2 = MagicMock()
        mock_ec2.get_paginator.return_value.paginate.return_value = [{
            "Reservations": [{"Instances": [{
                "InstanceId": "i-789", "InstanceType": "t3.large",
                "State": {"Name": "running"}, "Tags": []
            }]}]
        }]
        with patch("kloudkut.scanners.compute.get_client", return_value=mock_ec2), \
             patch("kloudkut.scanners.compute.get_avg", return_value=0.3), \
             patch("kloudkut.scanners.compute.get_sum", return_value=100.0):
            findings = EC2Scanner({"EC2": {"avgCpu": 1, "netInOut": 5000}},
                                  ["us-east-1"]).scan_region("us-east-1")
        assert len(findings) == 1
        assert "CPU" in findings[0].reason


class TestEBSScanner:
    def test_unattached_volume_flagged(self):
        from kloudkut.scanners.storage import EBSScanner
        mock_ec2 = MagicMock()
        mock_ec2.get_paginator.return_value.paginate.return_value = [{
            "Volumes": [{"VolumeId": "vol-123", "Size": 100, "Tags": []}]
        }]
        with patch("kloudkut.scanners.storage.get_client", return_value=mock_ec2):
            findings = EBSScanner({}, ["us-east-1"]).scan_region("us-east-1")
        assert len(findings) == 1
        assert findings[0].monthly_cost == 10.0
        assert "delete-volume" in findings[0].remediation

    def test_cost_proportional_to_size(self):
        from kloudkut.scanners.storage import EBSScanner
        mock_ec2 = MagicMock()
        mock_ec2.get_paginator.return_value.paginate.return_value = [{
            "Volumes": [{"VolumeId": "vol-456", "Size": 500, "Tags": []}]
        }]
        with patch("kloudkut.scanners.storage.get_client", return_value=mock_ec2):
            findings = EBSScanner({}, ["us-east-1"]).scan_region("us-east-1")
        assert findings[0].monthly_cost == 50.0


class TestEIPScanner:
    def test_unassociated_eip_flagged(self):
        from kloudkut.scanners.network import EIPScanner
        mock_ec2 = MagicMock()
        mock_ec2.describe_addresses.return_value = {
            "Addresses": [{"AllocationId": "eipalloc-123", "PublicIp": "1.2.3.4"}]
        }
        with patch("kloudkut.scanners.network.get_client", return_value=mock_ec2):
            findings = EIPScanner({}, ["us-east-1"]).scan_region("us-east-1")
        assert len(findings) == 1
        assert "release-address" in findings[0].remediation

    def test_associated_eip_not_flagged(self):
        from kloudkut.scanners.network import EIPScanner
        mock_ec2 = MagicMock()
        mock_ec2.describe_addresses.return_value = {
            "Addresses": [{"AllocationId": "eipalloc-456", "PublicIp": "1.2.3.5",
                           "AssociationId": "eipassoc-789"}]
        }
        with patch("kloudkut.scanners.network.get_client", return_value=mock_ec2):
            findings = EIPScanner({}, ["us-east-1"]).scan_region("us-east-1")
        assert findings == []


class TestRDSScanner:
    def test_zero_connections_flagged(self):
        from kloudkut.scanners.database import RDSScanner
        mock_rds = MagicMock()
        mock_rds.get_paginator.return_value.paginate.return_value = [{
            "DBInstances": [{"DBInstanceIdentifier": "db-1", "DBInstanceClass": "db.t3.micro",
                             "MultiAZ": False, "TagList": []}]
        }]
        with patch("kloudkut.scanners.database.get_client", return_value=mock_rds), \
             patch("kloudkut.scanners.database.get_avg", return_value=0.0):
            findings = RDSScanner({}, ["us-east-1"]).scan_region("us-east-1")
        assert len(findings) == 1
        assert findings[0].resource_id == "db-1"

    def test_active_db_not_flagged(self):
        from kloudkut.scanners.database import RDSScanner
        mock_rds = MagicMock()
        mock_rds.get_paginator.return_value.paginate.return_value = [{
            "DBInstances": [{"DBInstanceIdentifier": "db-2", "DBInstanceClass": "db.t3.micro",
                             "MultiAZ": False, "TagList": []}]
        }]
        with patch("kloudkut.scanners.database.get_client", return_value=mock_rds), \
             patch("kloudkut.scanners.database.get_avg", return_value=5.0):
            findings = RDSScanner({}, ["us-east-1"]).scan_region("us-east-1")
        assert findings == []


class TestS3Scanner:
    def test_empty_bucket_flagged(self):
        from kloudkut.scanners.storage import S3Scanner
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "my-bucket"}]}
        mock_s3.get_bucket_location.return_value = {"LocationConstraint": "us-east-1"}
        mock_s3.list_objects_v2.return_value = {"KeyCount": 0}
        with patch("kloudkut.scanners.storage.get_client", return_value=mock_s3):
            findings = S3Scanner({}, ["us-east-1"]).scan_region("us-east-1")
        assert len(findings) == 1
        assert "rb" in findings[0].remediation

    def test_bucket_in_different_region_skipped(self):
        from kloudkut.scanners.storage import S3Scanner
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "other-bucket"}]}
        mock_s3.get_bucket_location.return_value = {"LocationConstraint": "eu-west-1"}
        with patch("kloudkut.scanners.storage.get_client", return_value=mock_s3):
            findings = S3Scanner({}, ["us-east-1"]).scan_region("us-east-1")
        assert findings == []


class TestHistory:
    def test_save_and_trend(self, sample_findings, tmp_path):
        from kloudkut.core import history
        orig_db = history._DB
        history._DB = tmp_path / "test_history.db"
        try:
            history.save_scan(sample_findings)
            history.save_scan(sample_findings)
            trend = history.get_trend()
            assert len(trend) == 2
            assert trend[0]["monthly_savings"] == 455.0
        finally:
            history._DB = orig_db

    def test_delta_calculation(self, sample_findings, tmp_path):
        from kloudkut.core import history
        from kloudkut.core.scanner import Finding
        orig_db = history._DB
        history._DB = tmp_path / "test_delta.db"
        try:
            history.save_scan(sample_findings)
            bigger = sample_findings + [Finding("x", "x", "EC2", "us-east-1", "idle", 100.0)]
            history.save_scan(bigger)
            delta = history.get_delta()
            assert delta["delta"] == 100.0
        finally:
            history._DB = orig_db


class TestRemediation:
    def test_finding_has_remediation_field(self):
        f = Finding("id", "name", "EC2", "us-east-1", "idle", 100.0, remediation="aws ec2 stop-instances")
        assert f.remediation == "aws ec2 stop-instances"

    def test_finding_remediation_defaults_empty(self):
        f = Finding("id", "name", "EC2", "us-east-1", "idle", 100.0)
        assert f.remediation == ""
