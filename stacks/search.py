"""
AWS CDK Elasticsearch Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging
from typing import Optional

from aws_cdk import CfnOutput, Environment
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_opensearchservice as os
from constructs import Construct

from stacks.protected import NetworkProtectedStack
from stacks.settings import SearchMasterNodeCountSettings
from stacks.settings import SearchMasterNodeTypeSettings
from stacks.settings import SearchNodeCountSettings
from stacks.settings import SearchNodeTypeSettings
from stacks.settings import SearchVolumeSizeSettings

logger: logging.RootLogger = logging.getLogger(__name__)


class OpensearchStack(NetworkProtectedStack):
    """
    AWS Cloud Formation stack
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
            network=network,
            description=description,
            application=application,
            env=env,
        )

        # Application attributes.
        self._application: str = application
        self._network: str = network

        # Stack resources.
        self._sg: Optional[ec2.SecurityGroup] = None
        self._domain: Optional[os.CfnDomain] = None

    def export(self) -> None:
        """
        Exporting resources in this stack.
        """
        logger.info("Exporting resources.")
        CfnOutput(
            self,
            f"{self._application}::{self._network}::opensearch::host",
            export_name=f"{self._application}::{self._network}::opensearch::host",
            value=self._domain.attr_domain_endpoint,
        )

    def deploy(self) -> None:
        """
        Creating resources in this stack.
        """
        logger.info("Creating resources.")
        if not self._application:
            raise AttributeError("Unknown application name!")
        if not self._network:
            raise AttributeError("Unknown network name!")
        if not self.region:
            raise AttributeError("Unknown region name!")
        if not self._private_subnets:
            raise AttributeError("Private subnets not found!")
        self._create_sg()
        self._create_es()

    def _create_sg(self) -> None:
        """
        Creating an AWS Security Group allowing HTTPS access.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/SecurityGroup.html
        """
        logger.debug("Creating AWS Elasticsearch security group.")
        self._sg: ec2.SecurityGroup = ec2.SecurityGroup(
            self,
            f"{self._application}-{self._network}-os-security-group",
            vpc=self._vpc,
            allow_all_outbound=True,
        )
        self._sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443))

    def _create_es(self) -> None:
        """
        Creating an AWS Elasticsearch domain.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_opensearchservice/CfnDomain.html
        """
        logger.debug("Creating Elasticsearch domain.")
        self._domain: os.CfnDomain = os.CfnDomain(
            self,
            f"{self._application}-{self._network}-os-domain",
            domain_name=f"{self._application}-{self._network}-os-domain",
            ebs_options=os.CfnDomain.EBSOptionsProperty(
                ebs_enabled=True,
                volume_size=SearchVolumeSizeSettings.get(self._network),
            ),
            engine_version="OpenSearch_1.2",
            vpc_options=os.CfnDomain.VPCOptionsProperty(
                security_group_ids=[
                    self._sg.security_group_id,
                ],
                subnet_ids=[subnet.subnet_id for subnet in self._private_subnets][:1],
            ),
            cluster_config=os.CfnDomain.ClusterConfigProperty(
                dedicated_master_enabled=True,
                dedicated_master_count=SearchMasterNodeCountSettings.get(self._network),
                dedicated_master_type=SearchMasterNodeTypeSettings.get(self._network),
                instance_type=SearchNodeTypeSettings.get(self._network),
                instance_count=SearchNodeCountSettings.get(self._network),
            ),
            access_policies={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "es:*",
                        "Resource": "*",
                    }
                ],
            },
        )
