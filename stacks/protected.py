"""
AWS CDK Network Protected Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging
from typing import List, Optional

from aws_cdk import Environment, Fn
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

from stacks.base import BaseStack
from stacks.settings import AvailabilityZonesSettings
from stacks.settings import PrivateSubnetCidrSettings
from stacks.settings import PublicSubnetCidrSettings
from stacks.settings import VpcCidrSettings

logger: logging.RootLogger = logging.getLogger(__name__)


class NetworkProtectedStack(BaseStack):
    """
    Class that imports the VPC from the NetworkStack.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        application: str,
        description: str,
        network: str,
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
            env=env,
        )

        # Application attributes.
        self._application: str = application
        self._network: str = network

        # Imported resources.
        self._vpc: Optional[ec2.Vpc] = None
        self._public_subnets: List[ec2.Subnet] = []
        self._private_subnets: List[ec2.Subnet] = []

    def load(self) -> None:
        """
        Importing resources in this stack.
        """
        logger.info("Importing resources at: %s.", self)
        super().load()
        if not self._application:
            raise AttributeError("Unknown application name!")
        if not self._network:
            raise AttributeError("Unknown network name!")
        if not self.region:
            raise AttributeError("Unknown region name!")
        self._import_vpc()
        self._import_public_subnets()
        self._import_private_subnets()

    def _import_vpc(self) -> None:
        """
        Importing AWS VPC.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/Vpc.html
        """
        logger.debug("Importing AWS VPC: %s - %s.", self._application, self._network)
        if not self._network:
            raise AttributeError("Network not loaded")
        self._vpc: ec2.Vpc = ec2.Vpc.from_vpc_attributes(
            self,
            f"{self._application}-{self._network}-vpc",
            vpc_id=Fn.import_value(f"{self._application}::{self._network}::vpc::id"),
            vpc_cidr_block=VpcCidrSettings.get(self._network),
            availability_zones=AvailabilityZonesSettings.get(self._network),
            public_subnet_ids=[
                Fn.import_value(f"{self._application}::{self._network}::subnet::public::{index + 1}::id")
                for index in range(len(PublicSubnetCidrSettings.get(self._network)))
            ],
            private_subnet_ids=[
                Fn.import_value(f"{self._application}::{self._network}::subnet::private::{index + 1}::id")
                for index in range(len(PrivateSubnetCidrSettings.get(self._network)))
            ],
        )

    def _import_public_subnets(self) -> None:
        """
        Importing AWS VPC public subnets.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/Subnet.html
        """
        logger.info("Importing AWS VPC public subnets")
        if not self.region:
            raise AttributeError("Region is empty!")
        if not self._network:
            raise AttributeError("Network is empty!")
        if not self._application:
            raise AttributeError("Application is empty!")
        availability_zones: List[str] = AvailabilityZonesSettings.cycle(self._network)
        self._public_subnets: List[ec2.Subnet] = [
            ec2.Subnet.from_subnet_attributes(
                self,
                f"{self._application}::{self._network}::subnet::public::{index + 1}::id",
                subnet_id=Fn.import_value(f"{self._application}::{self._network}::subnet::public::{index + 1}::id"),
                availability_zone=f"{self.region}{next(availability_zones)}",
            )
            for index in range(PublicSubnetCidrSettings.length(self._network))
        ]

    def _import_private_subnets(self) -> None:
        """
        Importing AWS VPC private subnets.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/Subnet.html
        """
        logger.info("Importing AWS VPC private subnets")
        availability_zones: List[str] = AvailabilityZonesSettings.cycle(self._network)
        self._private_subnets: List[ec2.Subnet] = [
            ec2.Subnet.from_subnet_attributes(
                self,
                f"{self._application}::{self._network}::subnet::private::{index + 1}::id",
                subnet_id=Fn.import_value(f"{self._application}::{self._network}::subnet::private::{index + 1}::id"),
                availability_zone=f"{self.region}{next(availability_zones)}",
            )
            for index in range(PrivateSubnetCidrSettings.length(self._network))
        ]
