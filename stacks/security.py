"""
AWS CDK IAM Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging
from typing import Optional

from aws_cdk import CfnOutput, Environment
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from constructs import Construct

from stacks.protected import NetworkProtectedStack

logger: logging.RootLogger = logging.getLogger(__name__)


class SecurityStack(NetworkProtectedStack):
    """
    AWS Cloud Formation stack
    """

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
            description=description,
            network=network,
            application=application,
            env=env,
        )

        # Application attributes.
        self._application: str = application
        self._network: str = network

        # Stack resources.
        self._os_role: Optional[iam.CfnServiceLinkedRole] = None
        self._ec2_profile: Optional[iam.CfnInstanceProfile] = None
        self._bastion_role: Optional[iam.Role] = None
        self._ec2_role: Optional[iam.Role] = None
        self._elb_role: Optional[iam.Role] = None
        self._ec2_sg: Optional[ec2.SecurityGroup] = None
        self._elb_sg: Optional[ec2.SecurityGroup] = None

    def deploy(self) -> None:
        """
        Creating resources in this stack.
        """
        logger.debug("Creating AWS IAM Roles & Policies.")
        if not self._application:
            raise AttributeError("Unknown application name!")
        if not self._network:
            raise AttributeError("Unknown network name!")
        self._create_elb_role()
        self._create_bastion_role()
        self._create_ec2_role()
        self._create_ec2_profile()
        self._create_os_role()
        self._create_ec2_sg()
        self._create_elb_sg()

    def export(self) -> None:
        """
        Exporting resources in this stack.
        """
        logger.info("Exporting resources.")
        CfnOutput(
            self,
            f"{self._application}::{self._network}::application::ec2::role::name",
            export_name=f"{self._application}::{self._network}::application::ec2::role::name",
            value=self._ec2_role.role_name,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::application::bastion::role::name",
            export_name=f"{self._application}::{self._network}::application::bastion::role::name",
            value=self._bastion_role.role_name,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::application::ec2::profile::name",
            export_name=f"{self._application}::{self._network}::application::ec2::profile::name",
            value=self._ec2_profile.instance_profile_name,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::application::elb::role::name",
            export_name=f"{self._application}::{self._network}::application::elb::role::name",
            value=self._elb_role.role_name,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::application::ec2::sg::id",
            export_name=f"{self._application}::{self._network}::application::ec2::sg::id",
            value=self._ec2_sg.security_group_id,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::application::elb::sg::id",
            export_name=f"{self._application}::{self._network}::application::elb::sg::id",
            value=self._elb_sg.security_group_id,
        )

    def _create_ec2_profile(self) -> None:
        """
        Creating AWS Instance Profile
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_iam/CfnInstanceProfile.html
        """
        logger.debug("Creating AWS Instance Profile.")
        self._ec2_profile: iam.CfnInstanceProfile = iam.CfnInstanceProfile(
            self,
            f"{self._application}-{self._network}-ec2-instance-profile",
            instance_profile_name=f"{self._application}-{self._network}-ec2-instance-profile",
            roles=[
                self._ec2_role.role_name,
            ],
        )

    def _create_ec2_role(self) -> None:
        """
        Creating an AWS IAM Role.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_iam/Role.html

        Principals:
        https://gist.github.com/shortjared/4c1e3fe52bdfa47522cfe5b41e5d6f22

        Adding policies to the AWS EC2 role.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_iam/ManagedPolicy.html
        """
        logger.debug("Creating AWS EC2 Role.")
        self._ec2_role: iam.Role = iam.Role(
            self,
            f"{self._application}-{self._network}-ec2-iam-role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            role_name=f"{self._application}-{self._network}-ec2-iam-role",
            description=f"AWS IAM Role used by the EC2 instances at '{self._network}'.",
        )
        for policy in [
            "AWSElasticBeanstalkWebTier",
            "AWSElasticBeanstalkReadOnly",
            "SecretsManagerReadWrite",
            "AmazonS3FullAccess",
            "AWSLambdaExecute",
            "AmazonSESFullAccess",
            "AmazonSSMFullAccess",
            "AmazonAthenaFullAccess",
            "AmazonKinesisFullAccess",
            "EC2InstanceProfileForImageBuilderECRContainerBuilds",
        ]:
            self._ec2_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name(policy))

    def _create_bastion_role(self) -> None:
        """
        Creating an AWS IAM Role.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_iam/Role.html

        Principals:
        https://gist.github.com/shortjared/4c1e3fe52bdfa47522cfe5b41e5d6f22

        Adding policies to the AWS EC2 role.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_iam/ManagedPolicy.html
        """
        logger.debug("Creating AWS EC2 Role.")
        self._bastion_role: iam.Role = iam.Role(
            self,
            f"{self._application}-{self._network}-bastion-iam-role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            role_name=f"{self._application}-{self._network}-bastion-iam-role",
            description=f"AWS IAM Role used by the EC2 instances at '{self._network}'.",
        )
        for policy in [
            "AWSElasticBeanstalkWebTier",
            "AWSElasticBeanstalkReadOnly",
            "SecretsManagerReadWrite",
            "AmazonS3FullAccess",
            "AWSLambdaExecute",
            "AmazonSESFullAccess",
            "AmazonSSMFullAccess",
            "AmazonAthenaFullAccess",
            "AmazonKinesisFullAccess",
            "EC2InstanceProfileForImageBuilderECRContainerBuilds",
        ]:
            self._bastion_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name(policy))

    def _create_elb_role(self) -> None:
        """
        Creating an AWS ELB Role.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_iam/Role.html

        Principals:
        https://gist.github.com/shortjared/4c1e3fe52bdfa47522cfe5b41e5d6f22
        """
        logger.debug("Creating AWS ELB Role.")
        self._elb_role: iam.Role = iam.Role(
            self,
            f"{self._application}-{self._network}-elb-iam-role",
            assumed_by=iam.ServicePrincipal("elasticloadbalancing.amazonaws.com"),
            role_name=f"{self._application}-{self._network}-elb-iam-role",
            description=f"AWS IAM Role used by the EC2 instances at '{self._network}'.",
        )

    def _create_os_role(self) -> None:
        """
        Creating an AWS IAM Role.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_iam/CfnServiceLinkedRole.html
        """
        self._os_role: iam.CfnServiceLinkedRole = iam.CfnServiceLinkedRole(
            self,
            f"{self._application}-{self._network}-os-role",
            aws_service_name="es.amazonaws.com",
        )

    def _create_ec2_sg(self) -> None:
        """
        Creating an AWS Security Group.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/SecurityGroup.html
        """
        logger.debug("Creating AWS EC2 security group.")
        self._ec2_sg: ec2.SecurityGroup = ec2.SecurityGroup(
            self,
            f"{self._application}-{self._network}-ec2-security-group",
            vpc=self._vpc,
            allow_all_outbound=True,
        )
        self._ec2_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(80),
            description="Allow traffic on port 80 only within the AWS VPC",
        )
        self._ec2_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(22),
            description="Allow traffic on port 22 only within the AWS VPC",
        )

    def _create_elb_sg(self) -> None:
        """
        Creating an AWS Security Group.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/SecurityGroup.html
        """
        logger.debug("Creating AWS ELB security group.")
        self._elb_sg: ec2.SecurityGroup = ec2.SecurityGroup(
            self,
            f"{self._application}-{self._network}-elb-security-group",
            vpc=self._vpc,
            allow_all_outbound=True,
        )
        self._elb_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(80),
            description="Allow public traffic on port 80",
        )
        self._elb_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(443),
            description="Allow public traffic on port 443",
        )
