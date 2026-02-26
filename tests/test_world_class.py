"""Tests for new world-class features."""
import pytest
from kloudkut.core.telemetry import track_scan, get_metrics, get_summary, clear_metrics
from kloudkut.core.health import check_aws_credentials, get_system_status
from kloudkut.core.validation import (
    validate_region, validate_account_id, validate_service_name,
    sanitize_tag_key, sanitize_tag_value, validate_cost_threshold
)
from kloudkut.core.retry import retry_with_backoff
from kloudkut.core.scanner import BaseScanner, Finding
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError


class TestTelemetry:
    def test_track_scan_decorator(self):
        clear_metrics()
        
        class TestScanner(BaseScanner):
            service = "TEST"
            
            @track_scan
            def scan_region(self, region):
                return [Finding("id", "name", "TEST", region, "idle", 100.0)]
        
        scanner = TestScanner({}, ["us-east-1"])
        scanner.scan_region("us-east-1")
        
        metrics = get_metrics()
        assert len(metrics) == 1
        assert metrics[0]["service"] == "TEST"
        assert metrics[0]["region"] == "us-east-1"
        assert metrics[0]["findings"] == 1
    
    def test_get_summary(self):
        clear_metrics()
        
        class TestScanner(BaseScanner):
            service = "TEST"
            
            @track_scan
            def scan_region(self, region):
                return [Finding("id", "name", "TEST", region, "idle", 100.0)]
        
        scanner = TestScanner({}, ["us-east-1", "us-west-2"])
        scanner.scan_region("us-east-1")
        scanner.scan_region("us-west-2")
        
        summary = get_summary()
        assert summary["total_scans"] == 2
        assert summary["total_findings"] == 2
        assert summary["services_scanned"] == 1


class TestHealth:
    @patch("boto3.client")
    def test_check_aws_credentials_success(self, mock_client):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test"
        }
        mock_client.return_value = mock_sts
        
        result = check_aws_credentials()
        assert result["status"] == "healthy"
        assert result["account_id"] == "123456789012"
    
    @patch("boto3.client")
    def test_check_aws_credentials_failure(self, mock_client):
        mock_client.side_effect = Exception("No credentials")
        
        result = check_aws_credentials()
        assert result["status"] == "unhealthy"
        assert "error" in result


class TestValidation:
    def test_validate_region_valid(self):
        assert validate_region("us-east-1") is True
        assert validate_region("eu-west-2") is True
        assert validate_region("ap-south-1") is True
    
    def test_validate_region_invalid(self):
        assert validate_region("invalid") is False
        assert validate_region("us-east") is False
        assert validate_region("") is False
    
    def test_validate_account_id_valid(self):
        assert validate_account_id("123456789012") is True
    
    def test_validate_account_id_invalid(self):
        assert validate_account_id("12345") is False
        assert validate_account_id("abcdefghijkl") is False
    
    def test_validate_service_name_valid(self):
        assert validate_service_name("EC2") is True
        assert validate_service_name("RDS") is True
    
    def test_validate_service_name_invalid(self):
        assert validate_service_name("ec2") is False
        assert validate_service_name("123") is False
    
    def test_sanitize_tag_key(self):
        assert sanitize_tag_key("Environment") == "Environment"
        assert sanitize_tag_key("Env<script>") == "Envscript"
        assert sanitize_tag_key("a" * 200) == "a" * 128
    
    def test_sanitize_tag_value(self):
        assert sanitize_tag_value("production") == "production"
        assert sanitize_tag_value("prod<script>") == "prodscript"
    
    def test_validate_cost_threshold(self):
        assert validate_cost_threshold(100.0) is True
        assert validate_cost_threshold(0) is True
        assert validate_cost_threshold(-1) is False
        assert validate_cost_threshold(2000000) is False


class TestRetry:
    def test_retry_success_first_attempt(self):
        @retry_with_backoff(max_retries=3)
        def successful_call():
            return "success"
        
        result = successful_call()
        assert result == "success"
    
    def test_retry_throttling(self):
        call_count = [0]
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def throttled_call():
            call_count[0] += 1
            if call_count[0] < 3:
                error = ClientError(
                    {"Error": {"Code": "Throttling"}},
                    "operation"
                )
                raise error
            return "success"
        
        result = throttled_call()
        assert result == "success"
        assert call_count[0] == 3
    
    def test_retry_non_throttling_error(self):
        @retry_with_backoff(max_retries=3)
        def failing_call():
            error = ClientError(
                {"Error": {"Code": "AccessDenied"}},
                "operation"
            )
            raise error
        
        with pytest.raises(ClientError):
            failing_call()


class TestIntegration:
    def test_full_scan_with_telemetry(self):
        clear_metrics()
        
        class TestScanner(BaseScanner):
            service = "INTEGRATION"
            
            @track_scan
            def scan_region(self, region):
                return [
                    Finding("r1", "resource1", "INTEGRATION", region, "idle", 100.0),
                    Finding("r2", "resource2", "INTEGRATION", region, "idle", 200.0),
                ]
        
        scanner = TestScanner({}, ["us-east-1", "us-west-2"])
        findings = scanner.scan(use_cache=False)
        
        assert len(findings) == 4
        summary = get_summary()
        assert summary["total_scans"] == 2
        assert summary["total_findings"] == 4
