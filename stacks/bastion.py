"""
AWS CDK Network Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging
from typing import List, Optional

from aws_cdk import CfnOutput, Environment, Fn
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from constructs import Construct

from stacks.protected import NetworkProtectedStack
from stacks.settings import AvailabilityZonesSettings
from stacks.settings import BastionInstanceTypeSettings
from stacks.settings import ServerAmiSettings
from stacks.settings import ServerKeyPairSettings

logger: logging.RootLogger = logging.getLogger(__name__)


class BastionStack(NetworkProtectedStack):
    """
    AWS Cloud Formation stack
    """

    # This constant controls the maximum amount of bastion servers
    # regardless of the environment and its configuration.
    MAX_EC2_INSTANCES: int = 2

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        description: str,
        application: str,
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
            network=network,
            application=application,
            description=description,
            env=env,
        )

        # Application attributes.
        self._application: str = application
        self._network: str = network

        # Stack resources.
        self._ec2: List[ec2.Instance] = []
        self._sg: Optional[ec2.SecurityGroup] = None
        self._eip: List[ec2.CfnEIP] = []
        self._role: Optional[iam.Role] = None

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
        if not self._public_subnets:
            raise AttributeError("Public subnets not found!")
        self._create_sg()
        self._create_ec2()
        self._create_eip()

    def load(self) -> None:
        """
        Importing resources in this stack.
        """
        logger.info("Importing resources at: %s.", self)
        super().load()
        self._role: iam.Role = iam.Role.from_role_name(
            self,
            f"{self._application}::{self._network}::application::ec2::role::name",
            role_name=Fn.import_value(f"{self._application}::{self._network}::application::ec2::role::name"),
        )

    def export(self) -> None:
        """
        Exporting resources in this stack.
        """
        logger.info("Exporting resources.")
        for index, bastion in enumerate(self._ec2):
            CfnOutput(
                self,
                f"{self._application}::{self._network}::bastion::{index + 1}::ip",
                export_name=f"{self._application}::{self._network}::bastion::{index + 1}::ip",
                value=bastion.instance_public_ip,
            )

    def _create_sg(self) -> None:
        """
        Creating an AWS EC2 Security Group allowing SSH access.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/SecurityGroup.html
        """
        logger.debug("Creating AWS EC2 security group.")
        self._sg: ec2.SecurityGroup = ec2.SecurityGroup(
            self,
            f"{self._application}-{self._network}-bastion-security-group",
            vpc=self._vpc,
            allow_all_outbound=True,
        )
        self._sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(22),
            description="Allow public traffic on port 22 with the corresponding PEM file",
        )

    def _create_eip(self) -> None:
        """
        Creating an AWS EC2 Elastic IP for each bastion server.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/CfnEIP.html
        """
        logger.debug("Creating AWS EC2 elastic IPs.")
        for index, bastion in enumerate(self._ec2):
            eip: ec2.CfnEIP = ec2.CfnEIP(
                self,
                f"{self._application}-{self._network}-elastic-ip-{index + 1}",
                instance_id=bastion.instance_id,
            )
            self._eip.append(eip)

    def _get_user_data(self) -> ec2.UserData:
        """
        Returns the UserData object that is preloaded into the EC2.
        """
        commands: ec2.UserData = ec2.UserData.for_linux()
        commands.add_commands(
            # Updating the operating system.
            "sudo apt-get update -y",

            # Installing Ubuntu libraries.
            "sudo apt-get install -y gcc",
            "sudo apt-get install -y libmysqlclient-dev",
            "sudo apt-get install -y curl --fix-missing",

            # Installing Python libraries.
            "sudo apt-get install -y python3 python3-pip",
            "sudo pip install setuptools",
            "sudo pip install --upgrade pip",

            # Installing Node dependencies.
            "curl -sL https://deb.nodesource.com/setup_18.x | sudo bash -",
            "sudo apt-get install -y nodejs",
            "sudo npm install --global yarn",

            # Installing AWS libraries.
            "curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip'",
            "unzip awscliv2.zip",
            "sudo ./aws/install",
            "sudo apt-get install -y awscli",

            # Adding `set -o vi` to all shell sessions.
            "echo 'set -o vi >> ~.bashrc'",

            # Adding environment variables.
        )
        return commands

    def _create_ec2(self) -> None:
        """
        Creating an AWS EC2 Elastic IP.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/Instance.html
        """
        logger.debug("Creating AWS EC2 instances.")
        if not self._sg:
            raise RuntimeError("The security group for the bastion server has not been created!")
        if not self._role:
            raise RuntimeError("EC2 role not found!")
        availability_zones: List[str] = AvailabilityZonesSettings.cycle(self._network)
        for index, subnet in enumerate(self._public_subnets[: self.MAX_EC2_INSTANCES]):
            az: str = f"{self.region}{next(availability_zones)}"
            logger.debug("Creating the #%s bastion server at %s", index + 1, az)
            bastion: ec2.Instance = ec2.Instance(
                self,
                f"{self._application}-{self._network}-bastion-{index + 1}",
                instance_name=f"{self._application}-{self._network}-bastion-{index + 1}",
                instance_type=BastionInstanceTypeSettings.get(self._network),
                availability_zone=az,
                role=self._role,
                key_name=ServerKeyPairSettings.get(self._network),
                vpc=self._vpc,
                machine_image=ec2.MachineImage.generic_linux(
                    ami_map={
                        self.region: ServerAmiSettings.get(self._network),
                    },
                ),
                user_data=self._get_user_data(),
                user_data_causes_replacement=False,
                security_group=self._sg,
                block_devices=[
                    ec2.BlockDevice(
                        device_name="/dev/sda1",
                        volume=ec2.BlockDeviceVolume.ebs(48),
                    )
                ],
                vpc_subnets=ec2.SubnetSelection(
                    subnets=[
                        subnet,
                    ],
                ),
            )
            self._ec2.append(bastion)
