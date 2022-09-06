"""
AWS CDK Registry Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging
import os
from typing import Optional

from aws_cdk import CfnOutput, Environment
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

from stacks.base import BaseStack

logger: logging.RootLogger = logging.getLogger(__name__)


class RegistryStack(BaseStack):
    """
    AWS Cloud Formation stack
    """

    def __init__(
        self,
        scope: Construct,
        description: str,
        construct_id: str,
        application: str,
        environment: str,
        profile: str,
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
        self._environment: str = environment
        self._profile: str = profile

        # Stack resources.
        self._repository: Optional[ecr.Repository] = None
        self._bucket: Optional[s3.Bucket] = None

    def deploy(self) -> None:
        """
        Creating resources in this stack.
        """
        logger.info("Creaitng resources.")
        self._create_repository()
        self._create_bucket()
        self._upload_json()

    def export(self) -> None:
        """
        Exporting resources in this stack.
        """
        logger.info("Exporting resources.")
        CfnOutput(
            self,
            f"{self._application}::deployments::bucket::name",
            export_name=f"{self._application}::deployments::bucket::name",
            value=self._bucket.bucket_name,
        )
        CfnOutput(
            self,
            f"{self._application}::ecr::uri",
            export_name=f"{self._application}::ecr::uri",
            value=self._repository.repository_uri,
        )
        CfnOutput(
            self,
            f"{self._application}::ecr::name",
            export_name=f"{self._application}::ecr::name",
            value=self._repository.repository_name,
        )

    def _create_repository(self) -> None:
        """
        Creating an AWS ECR repository.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ecr/Repository.html
        """
        logger.info("Creaitng AWS ECR repository.")
        if not self._application:
            raise AttributeError("Unknown application name!")
        self._repository: ecr.Repository = ecr.Repository(
            self,
            self._application,
            repository_name=self._application,
        )

    def _create_bucket(self) -> None:
        """
        Creating an AWS S3 Bucket.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_s3/Bucket.html
        """
        logger.info("Creaitng AWS S3 bucket.")
        if not self.account:
            raise AttributeError("Unknown account name!")
        self._bucket: s3.Bucket = s3.Bucket(
            self,
            f"{self._application}-{self.account}-deployments-bucket",
            bucket_name=self._get_bucket_name(),
            versioned=True,
        )

    def _get_bucket_name(self) -> str:
        """
        Defines the name of the S3 Bucket.
        """
        return f"{self._application}-{self.account}-deployments-bucket"

    def _get_template(self) -> dict:
        """
        This generates a JSON file for deploying to Elastic Beanstalk from AWS ECR.
        https://stackoverflow.com/questions/54206071/aws-elastic-beanstalk-docker-from-ecr-error-no-docker-image-specified-in-docker
        """
        if not self._environment:
            raise AttributeError("Missing environment name!")
        if not self._application:
            raise AttributeError("Missing application name!")
        deployment: dict = {
            "AWSEBDockerrunVersion": "1",
            "Image": {
                "Name": f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{self._application}:{self._environment}",
                "Update": "true",
            },
            "Ports": [
                {
                    "ContainerPort": 80,
                    "HostPort": 80,
                }
            ],
            "Logging": "/var/log/nginx",
        }
        logger.debug("Deployment template: %s", deployment)
        return deployment

    def _upload_json(self) -> str:
        """
        Registering app into AWS S3.
        https://docs.aws.amazon.com/cdk/api/v1/docs/aws-s3-deployment-readme.html
        """
        logger.debug("Deploying application JSON into AWS S3")
        if not self._bucket:
            raise AttributeError("Bucket not created!")
        s3deploy.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[
                s3deploy.Source.json_data("Dockerrun.aws.json", self._get_template()),
            ],
            prune=False,
            destination_bucket=self._bucket,
            destination_key_prefix=os.path.join(self._environment),
        )
