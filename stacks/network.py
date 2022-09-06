"""
AWS CDK Network Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging
from typing import List, Optional

from aws_cdk import CfnOutput, Environment
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

from stacks.base import BaseStack
from stacks.settings import AvailabilityZonesSettings
from stacks.settings import PrivateSubnetCidrSettings
from stacks.settings import PublicSubnetCidrSettings
from stacks.settings import VpcCidrSettings

logger: logging.RootLogger = logging.getLogger(__name__)


class NetworkStack(BaseStack):
    """
    AWS Cloud Formation stack
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        application: str,
        network: str,
        env: Environment,
        **kwargs,
    ) -> None:
        """
        Stack constructor.
        """
        super().__init__(scope, construct_id, env=env)

        # Application attributes.
        self._application: str = application
        self._network: str = network

        # Stack resources.
        self._vpc: Optional[ec2.Vpc] = None
        self._public_subnets: List[ec2.Subnet] = []
        self._private_subnets: List[ec2.Subnet] = []
        self._nat_gateways: List[ec2.CfnNatGateway] = []
        self._igw: Optional[ec2.CfnInternetGateway] = None
        self._eip: List[ec2.CfnEIP] = []

    def export(self) -> None:
        """
        Exporting resources in this stack.
        """
        logger.info("Exporting resources.")
        CfnOutput(
            self,
            f"{self._application}::{self._network}::vpc::id",
            export_name=f"{self._application}::{self._network}::vpc::id",
            value=self._vpc.vpc_id,
        )
        for index, subnet in enumerate(self._public_subnets):
            CfnOutput(
                self,
                f"{self._application}::{self._network}::subnet::public::{index + 1}::id",
                export_name=f"{self._application}::{self._network}::subnet::public::{index + 1}::id",
                value=subnet.subnet_id,
            )
        for index, subnet in enumerate(self._private_subnets):
            CfnOutput(
                self,
                f"{self._application}::{self._network}::subnet::private::{index + 1}::id",
                export_name=f"{self._application}::{self._network}::subnet::private::{index + 1}::id",
                value=subnet.subnet_id,
            )

    def deploy(self) -> None:
        """
        Creating resources in this stack.
        """
        logger.info("Creaitng resources.")
        if not self._application:
            raise AttributeError("Unknown application name!")
        if not self._network:
            raise AttributeError("Unknown network name!")
        if not self.region:
            raise AttributeError("Unknown region name!")
        self._create_vpc()
        self._create_public_subnets()
        self._create_private_subnets()
        self._create_internet_gateway()
        self._create_eip()
        self._create_nat_gateways()
        self._create_vpc_endpoints()

    def _create_vpc(self) -> None:
        """
        Creating an AWS VPC.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/Vpc.html
        """
        logger.debug("Creating AWS VPC.")
        self._vpc: ec2.Vpc = ec2.Vpc(
            self,
            f"{self._application}-{self._network}-vpc",
            subnet_configuration=[],
            nat_gateways=0,
            nat_gateway_subnets=None,
            cidr=VpcCidrSettings.get(self._network),
            vpc_name=f"{self._application}-{self._network}-vpc",
            max_azs=AvailabilityZonesSettings.length(self._network),
        )

    def _create_public_subnets(self) -> None:
        """
        Creating public AWS VPC subnets.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/Subnet.html
        """
        logger.debug("Creating AWS VPC public subnets.")
        vpc_cidr: str = VpcCidrSettings.get(self._network)
        cidr_blocks: List[str] = PublicSubnetCidrSettings.get(self._network)
        availability_zones: List[str] = AvailabilityZonesSettings.cycle(self._network)
        for index, cidr_block in enumerate(cidr_blocks):
            logger.debug("Creating public subnet: %s (#%s)", cidr_block, index)
            if cidr_block.split(".")[:2] != vpc_cidr.split(".")[:2]:
                raise RuntimeError("The VPC CIDR and the subnet CIDR don't mwatch!")
            subnet: ec2.Subnet = ec2.Subnet(
                self,
                f"{self._application}-{self._network}-public-subnet-{index + 1}",
                cidr_block=cidr_block,
                vpc_id=self._vpc.vpc_id,
                availability_zone=f"{self.region}{next(availability_zones)}",
            )
            self._public_subnets.append(subnet)

    def _create_private_subnets(self) -> None:
        """
        Creating private AWS VPC subnets.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/Subnet.html
        """
        logger.debug("Creating AWS VPC private subnets.")
        vpc_cidr: str = VpcCidrSettings.get(self._network)
        cidr_blocks: List[str] = PrivateSubnetCidrSettings.get(self._network)
        availability_zones: List[str] = AvailabilityZonesSettings.cycle(self._network)
        for index, cidr_block in enumerate(cidr_blocks):
            logger.debug("Creating private subnet: %s (#%s)", cidr_block, index)
            if cidr_block.split(".")[:2] != vpc_cidr.split(".")[:2]:
                raise RuntimeError("The VPC CIDR and the subnet CIDR don't mwatch!")
            subnet: ec2.Subnet = ec2.Subnet(
                self,
                f"{self._application}-{self._network}-private-subnet-{index + 1}",
                cidr_block=cidr_block,
                vpc_id=self._vpc.vpc_id,
                availability_zone=f"{self.region}{next(availability_zones)}",
            )
            self._private_subnets.append(subnet)

    def _create_eip(self) -> None:
        """
        Creating an AWS EC2 Elastic IP for each NAT Gateway.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/CfnEIP.html
        """
        logger.debug("Creating AWS EC2 elastic IPs.")
        cidr_blocks: List[str] = PrivateSubnetCidrSettings.get(self._network)
        for index, _ in enumerate(cidr_blocks):
            eip: ec2.CfnEIP = ec2.CfnEIP(
                self,
                f"{self._application}-{self._network}-nat-ip-{index + 1}",
            )
            self._eip.append(eip)

    def _create_nat_gateways(self) -> None:
        """
        Creating AWS NAT Gateways.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/CfnNatGateway.html
        """
        logger.debug("Creating AWS VPC NAT gateways.")
        if not self._eip:
            raise AttributeError("AWS Elastic IPs not created!")
        for index, subnet in enumerate(self._private_subnets):
            nat: ec2.CfnNatGateway = ec2.CfnNatGateway(
                self,
                f"{self._application}-{self._network}-nat-{index + 1}",
                allocation_id=self._eip[index].attr_allocation_id,
                subnet_id=self._public_subnets[index].subnet_id,
                connectivity_type="public",
            )
            self._nat_gateways.append(nat)
            self._private_subnets[index].add_default_nat_route(nat.ref)

    def _create_internet_gateway(self) -> None:
        """
        Creating AWS IGW Gateway.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/CfnInternetGateway.html
        """
        logger.debug("Creating AWS VPC internet gateways.")
        self._igw: ec2.CfnInternetGateway = ec2.CfnInternetGateway(
            self,
            f"{self._application}-{self._network}-internet-gateway",
        )
        for index, subnet in enumerate(self._public_subnets):
            attachment: ec2.CfnVPCGatewayAttachment = ec2.CfnVPCGatewayAttachment(
                self,
                f"{self._application}-{self._network}-igw-attachment-{index + 1}",
                vpc_id=self._vpc.vpc_id,
                internet_gateway_id=self._igw.ref,
            )
            subnet.add_default_internet_route(self._igw.ref, attachment)

    def _create_vpc_endpoints(self) -> None:
        """
        Creating AWS VPC endpoints.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/InterfaceVpcEndpointService.html
        """
        logger.debug("Creating AWS VPC endpoints.")
        if not self._vpc:
            raise AttributeError("VPC not created!")
        if not self._private_subnets:
            raise AttributeError("Private subnets not created!")
        ec2.InterfaceVpcEndpoint(
            self,
            f"{self._application}-{self._network}-eb-health-vpc-endpoint",
            vpc=self._vpc,
            service=ec2.InterfaceVpcEndpointService(f"com.amazonaws.{self.region}.elasticbeanstalk-health"),
            subnets=ec2.SubnetSelection(subnets=self._private_subnets),
        )
        ec2.InterfaceVpcEndpoint(
            self,
            f"{self._application}-{self._network}-eb-vpc-endpoint",
            vpc=self._vpc,
            service=ec2.InterfaceVpcEndpointService(f"com.amazonaws.{self.region}.elasticbeanstalk"),
            subnets=ec2.SubnetSelection(subnets=self._private_subnets),
        )
        ec2.InterfaceVpcEndpoint(
            self,
            f"{self._application}-{self._network}-s3-vpc-endpoint",
            vpc=self._vpc,
            service=ec2.InterfaceVpcEndpointService(f"com.amazonaws.{self.region}.s3"),
            subnets=ec2.SubnetSelection(subnets=self._private_subnets),
        )
        ec2.InterfaceVpcEndpoint(
            self,
            f"{self._application}-{self._network}-redis-vpc-endpoint",
            vpc=self._vpc,
            service=ec2.InterfaceVpcEndpointService(f"com.amazonaws.{self.region}.elasticache"),
            subnets=ec2.SubnetSelection(subnets=self._private_subnets),
        )
