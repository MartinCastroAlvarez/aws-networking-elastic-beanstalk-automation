"""
AWS CDK Database Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging
from typing import Optional

import boto3
from aws_cdk import CfnOutput, Environment
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from constructs import Construct

from stacks.protected import NetworkProtectedStack
from stacks.settings import DatabaseDeletionProtectionSettings
from stacks.settings import DatabaseEncryptionSettings
from stacks.settings import DatabaseInstanceTypeSettings
from stacks.settings import DatabaseNameSettings
from stacks.settings import DatabaseSnapshotName
from stacks.settings import DatabaseStorageSize
from stacks.settings import DatabaseUsernameSettings

logger: logging.RootLogger = logging.getLogger(__name__)


class DatabaseStack(NetworkProtectedStack):
    """
    AWS Cloud Formation stack
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        application: str,
        description: str,
        profile: str,
        network: str,
        database: str,
        env: Environment,
        **kwargs,
    ) -> None:
        """
        Stack constructor.
        """
        super().__init__(
            scope,
            construct_id,
            description=description,
            network=network,
            profile=profile,
            application=application,
            env=env,
        )

        # Application attributes.
        self._application: str = application
        self._database: str = database
        self._network: str = network
        self._profile: str = profile

        # Stack resources.
        self._db: Optional[rds.DatabaseInstance] = None
        self._sg: Optional[ec2.SecurityGroup] = None

    def deploy(self) -> None:
        """
        Creating resources in this stack.
        """
        logger.info("Creating resources.")
        if not self._application:
            raise AttributeError("Unknown application name!")
        if not self._network:
            raise AttributeError("Unknown network name!")
        if not self._profile:
            raise AttributeError("Unknown profile name!")
        if not self._database:
            raise AttributeError("Unknown database name!")
        if not self.region:
            raise AttributeError("Unknown region name!")
        if not self._private_subnets:
            raise AttributeError("Private subnets not found!")
        self._create_sg()
        self._create_db()

    def export(self) -> None:
        """
        Exporting resources in this stack.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_secretsmanager/ISecret.html
        """
        logger.info("Exporting resources.")
        CfnOutput(
            self,
            f"{self._application}::{self._network}::{self._database}::database::host",
            export_name=f"{self._application}::{self._network}::{self._database}::database::host",
            value=self._db.db_instance_endpoint_address,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::{self._database}::database::port",
            export_name=f"{self._application}::{self._network}::{self._database}::database::port",
            value=self._db.db_instance_endpoint_port,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::{self._database}::database::secret",
            export_name=f"{self._application}::{self._network}::{self._database}::database::secret",
            value=self._db.secret.secret_name,
        )

    def _create_sg(self) -> None:
        """
        Creating an AWS RDS Security Group allowing MYSQL access.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/SecurityGroup.html
        """
        logger.debug("Creating AWS RDS security group.")
        self._sg: ec2.SecurityGroup = ec2.SecurityGroup(
            self,
            f"{self._application}-{self._network}-{self._database}-database-security-group",
            vpc=self._vpc,
            allow_all_outbound=True,
        )
        self._sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(3306))

    def _get_common_rds_config(self) -> dict:
        """
        Generates an object that is shared between ARS RDS instances
        that are created from scratch as well as those restored from a snapshot.
        """
        return {
            "engine": rds.DatabaseInstanceEngine.mysql(version=rds.MysqlEngineVersion.VER_8_0_28),
            "allocated_storage": DatabaseStorageSize.get(self._database),
            "instance_identifier": f"{self._application}-{self._network}-{self._database}-db",
            "instance_type": DatabaseInstanceTypeSettings.get(self._database),
            "deletion_protection": DatabaseDeletionProtectionSettings.get(self._database),
            "port": 3306,
            "vpc": self._vpc,
            "vpc_subnets": ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT),
            "security_groups": [
                self._sg,
            ],
        }

    def _snapshot_exists(self) -> bool:
        """
        Method responsible for listing the latest snapshots.

        Example:
        >>> {
        ...     'DBSnapshots': [
        ...         {
        ...             'DBSnapshotIdentifier': 'rds:devmartindb-2022-07-18-12-24',
        ...             'DBInstanceIdentifier': 'devmartindb',
        ...             'SnapshotCreateTime': datetime.datetime(2022, 7, 18, 12, 24, 58),
        ...             'Engine': 'mysql',
        ...             'AllocatedStorage': 30,
        ...             'Status': 'available',
        ...             'Port': 3306,
        ...             'AvailabilityZone': 'us-west-2b',
        ...             'VpcId': 'vpc-049e0f74083242701',
        ...             'InstanceCreateTime': datetime.datetime(2022, 7, 15, 21, 25, 43),
        ...             'MasterUsername': 'dcdata',
        ...             'EngineVersion': '8.0.28',
        ...             'LicenseModel': 'general-public-license',
        ...             'SnapshotType': 'automated',
        ...             'OptionGroupName': 'default:mysql-8-0',
        ...             'PercentProgress': 100,
        ...             'StorageType': 'gp2',
        ...             'Encrypted': True,
        ...             'KmsKeyId': 'arn:aws:kms:us-west-2:767087296931:key/7a69b',
        ...             'DBSnapshotArn': 'arn:aws:rds:us-west-2:767087296931:snapshot:rds:de...',
        ...             'IAMDatabaseAuthenticationEnabled': False,
        ...             'ProcessorFeatures': [],
        ...             'DbiResourceId': 'db-V4MHO2QLWJABKXXYGIQCYG5WDY',
        ...             'TagList': [],
        ...             'OriginalSnapshotCreateTime': datetime.datetime(2022, 7, 18, 12, 24, 58),
        ...             'SnapshotTarget': 'region'
        ...         }
        ...     ]
        ... }
        """
        name: str = DatabaseSnapshotName.get(self._network)
        logger.debug("Listing latest snapshots: %s", name)
        session: boto3.session.Session = boto3.session.Session(profile_name=self._profile)
        client: boto3.client = session.client("rds")
        try:
            response: dict = client.describe_db_snapshots(DBSnapshotIdentifier=name)
        except Exception as error:
            if "DBSnapshotNotFound" in str(error):
                logger.debug("DBSnapshotNotFound error: %s", name)
                return False
            raise
        for snapshot in response["DBSnapshots"]:
            if snapshot["Status"] == "available":
                logger.debug("Valid snapshot found: %s", snapshot)
                return True
            logger.debug("Snapshot found but not available: %s", snapshot)
            return False
        logger.debug("No snapshots found: %s", name)
        return False

    def _get_snapshot_arn(self) -> None:
        """
        This method generates a snapshot ARN that is used to define whether
        to create an AWS RDS instance from scratch or to restore the database
        from a snapshot.
        """
        return ":".join(
            ["arn", "aws", "rds", self.region, self.account, "snapshot", DatabaseSnapshotName.get(self._network)]
        )

    def _create_db(self) -> None:
        """
        Creating an AWS RDS instance.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_rds/DatabaseInstance.html
        """
        if self._snapshot_exists():
            self._create_db_from_snapshot()
        else:
            self._create_db_from_scratch()

    def _create_db_from_snapshot(self) -> None:
        """
        Creating an AWS RDS instance from snapshot.
        https://docs.aws.amazon.com/cdk/api/v1/docs/@aws-cdk_aws-rds.DatabaseInstanceFromSnapshot.html
        """
        logger.debug("Restoring database instance from snapshot.")
        self._db: rds.DatabaseInstanceFromSnapshot = rds.DatabaseInstanceFromSnapshot(
            self,
            f"{self._application}-{self._network}-{self._database}-db",
            snapshot_identifier=self._get_snapshot_arn(),
            credentials=rds.SnapshotCredentials.from_generated_password(
                username=DatabaseUsernameSettings.get(self._database),
            ),
            **self._get_common_rds_config(),
        )

    def _create_db_from_scratch(self) -> None:
        """
        Creating an AWS RDS instance from scratch.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_rds/DatabaseInstance.html
        """
        logger.debug("Creating database instance from scratch.")
        self._db: rds.DatabaseInstance = rds.DatabaseInstance(
            self,
            f"{self._application}-{self._network}-{self._database}-db",
            storage_encrypted=DatabaseEncryptionSettings.get(self._database),
            database_name=DatabaseNameSettings.get(self._database),
            credentials=rds.Credentials.from_generated_secret(
                username=DatabaseUsernameSettings.get(self._database),
                secret_name=f"{self._application}-{self._network}-{self._database}-database-credentials",
            ),
            **self._get_common_rds_config(),
        )
