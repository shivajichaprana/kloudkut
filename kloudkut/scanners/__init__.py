"""Scanner registry — all 45 services in one place."""
from kloudkut.scanners.compute import (
    EC2Scanner, LambdaScanner, ECSScanner, EKSScanner,
    EMRScanner, GlueScanner, LightsailScanner, CodeBuildScanner
)
from kloudkut.scanners.database import (
    RDSScanner, DynamoDBScanner, RedshiftScanner, ElastiCacheScanner,
    DocumentDBScanner, AuroraScanner, OpenSearchScanner, MSKScanner,
    ReservedInstanceScanner
)
from kloudkut.scanners.storage import (
    S3Scanner, EBSScanner, EFSScanner, FSxScanner, BackupScanner, ECRScanner
)
from kloudkut.scanners.network import (
    EIPScanner, LoadBalancerScanner, NATGatewayScanner, CloudFrontScanner,
    APIGatewayScanner, VPCEndpointScanner, Route53Scanner
)
from kloudkut.scanners.security import (
    GuardDutyScanner, WAFScanner, KMSScanner, SecretsManagerScanner,
    MacieScanner, SecurityHubScanner
)
from kloudkut.scanners.analytics import (
    KinesisScanner, SQSScanner, SNSScanner, StepFunctionsScanner,
    SageMakerScanner, AthenaScanner, CloudFormationScanner,
    EventBridgeScanner, CloudWatchAlarmsScanner, CloudWatchLogsScanner
)

ALL_SCANNERS = [
    # Compute
    EC2Scanner, LambdaScanner, ECSScanner, EKSScanner,
    EMRScanner, GlueScanner, LightsailScanner, CodeBuildScanner,
    # Database
    RDSScanner, DynamoDBScanner, RedshiftScanner, ElastiCacheScanner,
    DocumentDBScanner, AuroraScanner, OpenSearchScanner, MSKScanner,
    ReservedInstanceScanner,
    # Storage
    S3Scanner, EBSScanner, EFSScanner, FSxScanner, BackupScanner, ECRScanner,
    # Network
    EIPScanner, LoadBalancerScanner, NATGatewayScanner, CloudFrontScanner,
    APIGatewayScanner, VPCEndpointScanner, Route53Scanner,
    # Security
    GuardDutyScanner, WAFScanner, KMSScanner, SecretsManagerScanner,
    MacieScanner, SecurityHubScanner,
    # Analytics & Management
    KinesisScanner, SQSScanner, SNSScanner, StepFunctionsScanner,
    SageMakerScanner, AthenaScanner, CloudFormationScanner,
    EventBridgeScanner, CloudWatchAlarmsScanner, CloudWatchLogsScanner,
]

SCANNER_MAP: dict[str, type] = {s.service: s for s in ALL_SCANNERS}

__all__ = ["ALL_SCANNERS", "SCANNER_MAP"]
