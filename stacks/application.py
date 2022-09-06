"""
AWS CDK Elastic Beanstalk Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging
from typing import Optional

from aws_cdk import CfnOutput, Environment
from aws_cdk import aws_elasticbeanstalk as eb
from constructs import Construct

from stacks.base import BaseStack

logger: logging.RootLogger = logging.getLogger(__name__)


class ApplicationStack(BaseStack):
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
        self._app: Optional[eb.CfnApplication] = None

    def deploy(self) -> None:
        """
        Creating resources in this stack.
        """
        logger.debug("Creating AWS Elastic Beanstalk Application.")
        if not self._application:
            raise AttributeError("Unknown application name!")
        if not self._network:
            raise AttributeError("Unknown network name!")
        self._create_eb_app()

    def _create_eb_app(self) -> None:
        """
        Creating an AWS Elastic Beanstalk Application
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_elasticbeanstalk/CfnApplication.html
        """
        self._app: eb.CfnApplication = eb.CfnApplication(
            self,
            f"{self._application}-{self._network}-app",
            application_name=f"{self._application}-{self._network}-app",
        )

    def export(self) -> None:
        """
        Exporting resources in this stack.
        """
        logger.info("Exporting resources.")
        CfnOutput(
            self,
            f"{self._application}::{self._network}::application::name",
            export_name=f"{self._application}::{self._network}::application::name",
            value=self._app.application_name,
        )
