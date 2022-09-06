"""
Application configuration.
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging
from itertools import cycle
from typing import Any, List

from aws_cdk import aws_ec2 as ec2

logger: logging.RootLogger = logging.getLogger(__name__)


class Settings:
    """
    Parent class for settings.
    """

    @classmethod
    def get(cls, name: str) -> Any:
        """
        Fetches a config value from this settings class.
        """
        # Matching attribute by exact name.
        if hasattr(cls, name):
            logger.debug("Setting '%s': '%s'.", cls.__name__, getattr(cls, name))
            return getattr(cls, name)

        # Fallback to the default value.
        if hasattr(cls, "default"):
            logger.debug("Setting '%s': '%s'.", cls.__name__, getattr(cls, "default"))
            return getattr(cls, "default")

        # Neither the key nor a default value found.
        raise KeyError(f"Not supported by '{cls.__name__}': '{name}'.")

    @classmethod
    def cycle(cls, name: str) -> List[str]:
        """
        Iterates over a list of values infinitely.
        """
        value: Any = cls.get(name)
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"Expecting a list, got a {type(value)}")
        return cycle(value)

    @classmethod
    def length(cls, name: str) -> int:
        """
        Returns the size of a list.
        """
        value: Any = cls.get(name)
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"Expecting a list, got a {type(value)}")
        return len(value)


class VpcCidrSettings(Settings):
    """
    AWS VPC CIDR settings.
    """

    mainnet: str = "10.0.0.0/16"
    testnet: str = "10.1.0.0/16"
    devnet: str = "10.11.0.0/16"


class SharedCacheDatabaseSettings(Settings):
    """
    AWS VPC VPN Cache Database Settings
    """

    mainnet: bool = True
    testnet: bool = True
    devnet: bool = False


class PublicSubnetCidrSettings(Settings):
    """
    AWS VPC public subnets CIDR settings.
    https://www.davidc.net/sites/default/subnets/subnets.html?network=10.2.0.0&mask=16&division=15.7231
    """

    mainnet: List[str] = [
        "10.0.0.0/19",
        "10.0.32.0/19",
        "10.0.64.0/19",
    ]
    testnet: List[str] = [
        "10.1.0.0/19",
        "10.1.32.0/19",
    ]
    devnet: List[str] = [
        "10.11.0.0/19",
        "10.11.32.0/19",
    ]


class PrivateSubnetCidrSettings(Settings):
    """
    AWS VPC private subnets CIDR settings.
    https://www.davidc.net/sites/default/subnets/subnets.html?network=10.2.0.0&mask=16&division=15.7231
    """

    mainnet: List[str] = [
        "10.0.96.0/19",
        "10.0.128.0/19",
        "10.0.160.0/19",
    ]
    testnet: List[str] = [
        "10.1.64.0/19",
        "10.1.96.0/19",
    ]
    devnet: List[str] = [
        "10.11.64.0/19",
        "10.11.96.0/19",
    ]


class AvailabilityZonesSettings(Settings):
    """
    AWS VPC availability zones settings.
    """

    mainnet: List[str] = ["a", "b", "c"]
    testnet: List[str] = ["a", "b"]
    devnet: List[str] = ["a", "b"]


class CacheInstanceTypeSettings(Settings):
    """
    AWS Cache instance type settings.
    """

    mainnet: str = "cache.m6g.large"
    testnet: str = "cache.m6g.large"
    devnet: str = "cache.m6g.large"


class SearchVolumeSizeSettings(Settings):
    """
    AWS Opensearch volume size settings.
    """

    mainnet: int = 100
    testnet: int = 50
    devnet: int = 50


class SearchNodeTypeSettings(Settings):
    """
    AWS Elasticsearch node settings.
    """

    mainnet: str = "m5.large.search"
    testnet: str = "m5.large.search"
    devnet: str = "m5.large.search"


class SearchMasterNodeTypeSettings(Settings):
    """
    AWS Elasticsearch node settings.
    """

    mainnet: str = "m5.large.search"
    testnet: str = "m5.large.search"
    devnet: str = "m5.large.search"


class SearchNodeCountSettings(Settings):
    """
    AWS Elasticsearch node count settings.
    """

    mainnet: int = 3
    testnet: int = 3
    devnet: int = 3


class SearchMasterNodeCountSettings(Settings):
    """
    AWS Elasticsearch node count settings.
    """

    mainnet: int = 3
    testnet: int = 3
    devnet: int = 3


class DatabaseNameSettings(Settings):
    """
    AWS RDS database name settings.
    """

    proddb: str = "dcdata"
    demodb: str = "dcdata"
    default: str = "dcdata"


class DatabaseUsernameSettings(Settings):
    """
    AWS RDS username settings.
    """

    proddb: str = "dcdata"
    demodb: str = "dcdata"
    default: str = "dcdata"


class DatabaseEncryptionSettings(Settings):
    """
    Encryption at rest for RDS. Micro instances do not support this.
    """

    proddb: bool = True
    testnet: bool = True
    default: bool = False


class DatabaseDeletionProtectionSettings(Settings):
    """
    AWS RDS instance type settings.
    """

    proddb: bool = True
    demodb: bool = True
    default: bool = False


class MinNodesSettings(Settings):
    """
    AWS Ec2 instance count settings.
    """

    proddb: int = 4
    demodb: int = 2
    default: int = 1


class MaxNodesSettings(Settings):
    """
    AWS EC2 instance count settings.
    """

    proddb: int = 2
    demodb: int = 1
    default: int = 1


class DatabaseStorageSize(Settings):
    """
    AWS Database storage size
    """

    proddb: int = 100
    demodb: int = 50
    default: int = 30


class ServerAmiSettings(Settings):
    """
    AWS EC2 AMI settings.
    """

    production: str = "ami-075200050e2c8899b"
    default: str = "ami-075200050e2c8899b"


class BeanstalkServerAmiSettings(Settings):
    """
    AWS EC2 AMI settings.

    https://serverfault.com/questions/879694/network-problems-when-i-create-beanstalk-environments-from-an-ami

    AWS Elastic Beanstalk relies on a set of predefined scripts that are part of some specific AMIs.
    As a consequence, if you change this AMI but you choose an AMI without those Elastic Beanstalk
    scripts, then you will get an error message when Cloud Formation attempts to create your environment
    that indicates that the EC2 instances can not communicate with Elastic Beanstalk, even if there
    is a VPC Endpoint.
    """

    production: str = "ami-092fb6074c93dbeb3"
    default: str = "ami-092fb6074c93dbeb3"


class ServerKeyPairSettings(Settings):
    """
    AWS EC2 AMI settings.
    """

    mainnet: str = "MkpProduction"
    testnet: str = "MkpTesting"
    devnet: str = "MkpDevelopment"


class DatabaseSnapshotName(Settings):
    """
    Name of the snapshot to restore an AWS RDS
    instance from it.
    """

    mainnet: str = "latest"
    testnet: str = "latest"
    devnet: str = "latest"


class RollingUpdateRollingUpdateEnabledSettings(Settings):
    """
    Defines whether there is a rolling update policy or not.
    instance from it.
    """

    proddb: bool = True
    demodb: bool = True
    default: bool = False


class RollingUpdateMinInstancesInServiceSettings(Settings):
    """
    Minimum amount of instances in service during the
    deployment of Elastic Beanstalk.
    """

    proddb: int = 1
    demodb: int = 1


class RollingUpdateMaxBatchSizeSettings(Settings):
    """
    Maximum amount of instances during rolling updates.
    instance from it.
    """

    proddb: int = 1
    demodb: int = 1


class BeanstalkStorageSize(Settings):
    """
    Defines the EC2 instance volume size.
    """

    mainnet: int = 128
    testnet: int = 64
    devnet: int = 32


class DebugModeSettings(Settings):
    """
    Defines the EC2 debug mode.
    """

    mainnet: bool = False
    testnet: bool = True
    devnet: bool = True


class BeanstalkLoadBalancerSchemeSettings(Settings):
    """
    Defines whether the Load Balancer is 'public' or 'internal'
    in the Elastic Beanstalk environment.
    """

    mainnet: str = "public"
    testnet: str = "public"
    devnet: str = "public"


class BeanstalkInstanceTypeSettings(Settings):
    """
    AWS EC2 instance type settings.
    https://aws.amazon.com/es/ec2/instance-types/
    https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/InstanceSize.html
    https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/InstanceClass.html
    """

    mainnet: ec2.InstanceType = ec2.InstanceType.of(
        ec2.InstanceClass.STANDARD6_GRAVITON,
        ec2.InstanceSize.LARGE,
    )
    testnet: ec2.InstanceType = ec2.InstanceType.of(
        ec2.InstanceClass.BURSTABLE3,
        ec2.InstanceSize.MEDIUM,
    )
    default: ec2.InstanceType = ec2.InstanceType.of(
        ec2.InstanceClass.BURSTABLE3,
        ec2.InstanceSize.MEDIUM,
    )


class DatabaseInstanceTypeSettings(Settings):
    """
    AWS RDS instance type settings.
    https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/InstanceSize.html
    https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/InstanceClass.html
    """

    proddb: ec2.InstanceType = ec2.InstanceType.of(
        ec2.InstanceClass.STANDARD6_GRAVITON,
        ec2.InstanceSize.LARGE,
    )
    testnet: ec2.InstanceType = ec2.InstanceType.of(
        ec2.InstanceClass.STANDARD3,
        ec2.InstanceSize.MEDIUM,
    )
    default: ec2.InstanceType = ec2.InstanceType.of(
        ec2.InstanceClass.BURSTABLE4_GRAVITON,
        ec2.InstanceSize.SMALL,
    )


class BastionInstanceTypeSettings(Settings):
    """
    AWS EC2 instance type settings.
    https://aws.amazon.com/es/ec2/instance-types/
    https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/InstanceSize.html
    https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/InstanceClass.html
    """

    mainnet: ec2.InstanceType = ec2.InstanceType.of(
        ec2.InstanceClass.STANDARD6_GRAVITON,
        ec2.InstanceSize.SMALL,
    )
    testnet: ec2.InstanceType = ec2.InstanceType.of(
        ec2.InstanceClass.BURSTABLE4_GRAVITON,
        ec2.InstanceSize.SMALL,
    )
    default: ec2.InstanceType = ec2.InstanceType.of(
        ec2.InstanceClass.BURSTABLE4_GRAVITON,
        ec2.InstanceSize.SMALL,
    )


class HttpsCertificateSettings(Settings):
    """
    SSL Certificate for the HTTPS connection.
    """

    mainnet: str = 'certificate/83d034f3-ec71-4d6a-840e-a34ccdb052cd'
    testnet: str = 'certificate/6c014fbb-479c-499d-b976-13b4452582a0'
    devnet: str = 'certificate/89b1b8e2-926a-4aae-a9b6-42d3f2dbe485'
