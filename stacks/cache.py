"""
AWS CDK Cache Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging
from typing import Optional

from aws_cdk import CfnOutput, Environment
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticache as cache
from constructs import Construct

from stacks.protected import NetworkProtectedStack
from stacks.settings import CacheInstanceTypeSettings

logger: logging.RootLogger = logging.getLogger(__name__)


class CacheStack(NetworkProtectedStack):
    """
    AWS Cloud Formation stack
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        database: str,
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
        self._cluster: Optional[cache.CfnCacheCluster] = None
        self._sg: Optional[ec2.SecurityGroup] = None
        self._group: Optional[cache.CfnSubnetGroup] = None

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
        self._create_subnet_group()
        self._create_cluster()

    def export(self) -> None:
        """
        Exporting resources in this stack.
        """
        logger.info("Exporting resources.")
        CfnOutput(
            self,
            f"{self._application}::{self._network}::cache::host",
            export_name=f"{self._application}::{self._network}::cache::host",
            value=self._cluster.attr_redis_endpoint_address,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::cache::port",
            export_name=f"{self._application}::{self._network}::cache::port",
            value=self._cluster.attr_redis_endpoint_port,
        )

    def _create_subnet_group(self) -> None:
        """
        Creating an AWS Subnet Group.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_elasticache/CfnSubnetGroup.html
        """
        logger.debug("Creating Subnet Group.")
        if not self._private_subnets:
            raise AttributeError("No private subnets found!")
        self._group: cache.CfnSubnetGroup = cache.CfnSubnetGroup(
            self,
            f"{self._application}-{self._network}-redis-subnet-group",
            cache_subnet_group_name=f"{self._application}-{self._network}-redis-subnet-group",
            description=f"{self._application}-{self._network}-redis-subnet-group",
            subnet_ids=[subnet.subnet_id for subnet in self._private_subnets],
        )

    def _create_sg(self) -> None:
        """
        Creating an AWS Security Group allowing Redis access.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/SecurityGroup.html
        """
        logger.debug("Creating Redis security group.")
        self._sg: ec2.SecurityGroup = ec2.SecurityGroup(
            self,
            f"{self._application}-{self._network}-cache-security-group",
            vpc=self._vpc,
            allow_all_outbound=True,
        )
        self._sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(6379))

    def _create_cluster(self) -> None:
        """
        Creating an AWS Elastic Cache cluster.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_elasticache/CfnCacheCluster.html
        """
        logger.debug("Creating cluster instance.")
        self._cluster: cache.CfnCacheCluster = cache.CfnCacheCluster(
            self,
            f"{self._application}-{self._network}-cluster",
            cache_node_type=CacheInstanceTypeSettings.get(self._network),
            engine="redis",
            num_cache_nodes=1,  # Must be 1 for Redis.
            cache_subnet_group_name=self._group.cache_subnet_group_name,
            auto_minor_version_upgrade=False,
            cluster_name=f"{self._application}-{self._network}-cluster",
            port=6379,
            vpc_security_group_ids=[
                self._sg.security_group_id,
            ],
        )
