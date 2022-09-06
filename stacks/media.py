"""
AWS CDK Media Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging
from typing import Optional

from aws_cdk import CfnOutput, Environment
from aws_cdk import aws_cloudfront as cdn
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from constructs import Construct

from stacks.base import BaseStack

logger: logging.RootLogger = logging.getLogger(__name__)


class MediaStack(BaseStack):
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
        self._bucket: Optional[s3.Bucket] = None
        self._distribution: Optional[cdn.Distribution] = None

    def export(self) -> None:
        """
        Exporting resources in this stack.
        """
        logger.info("Exporting resources.")
        CfnOutput(
            self,
            f"{self._application}::{self._network}::bucket::name",
            export_name=f"{self._application}::{self._network}::bucket::name",
            value=self._bucket.bucket_name,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::cdn::domain",
            export_name=f"{self._application}::{self._network}::cdn::domain",
            value=self._distribution.domain_name,
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
        self._create_bucket()
        self._create_distribution()

    def _create_bucket(self) -> None:
        """
        Creating an AWS Bucket to upload media.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_s3/Bucket.html
        """
        logger.debug("Creating AWS S3 Bucket.")
        self._bucket: s3.Bucket = s3.Bucket(
            self,
            f"{self._application}-{self._network}-s3-bucket",
            bucket_name=f"{self._application}-{self._network}-s3-bucket",
            access_control=s3.BucketAccessControl.PUBLIC_READ,
            website_error_document="404.html",
            website_index_document="index.html",
            public_read_access=True,
        )

    def _create_distribution(self) -> None:
        """
        Creating an AWS CDN Distribution.
        https://docs.aws.amazon.com/cdk/api/v1/docs/@aws-cdk_aws-cloudfront.Distribution.html
        """
        logger.debug("Creating AWS CDN Distriubtion.")
        self._distribution: cdn.Distribution = cdn.Distribution(
            self,
            f"{self._application}-{self._network}-cdn",
            default_behavior=cdn.BehaviorOptions(origin=origins.S3Origin(self._bucket)),
            enabled=True,
            domain_names=[],
        )
