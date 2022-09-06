"""
AWS CDK Base Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import logging

from aws_cdk import Environment, Stack
from constructs import Construct

logger: logging.RootLogger = logging.getLogger(__name__)


class BaseStack(Stack):
    """
    AWS Cloud Formation stack
    """

    def __init__(self, scope: Construct, construct_id: str, env: Environment, **kwargs) -> None:
        """
        Stack constructor.
        """
        super().__init__(scope, construct_id, env=env)

    def __repr__(self) -> str:
        """
        String serializer.
        """
        return self.__class__.__name__

    def load(self) -> None:
        """
        Importing resources into this stack.
        """

    def deploy(self) -> None:
        """
        Creating resources in this stack.
        """

    def export(self) -> None:
        """
        Exporting resources in this stack.
        """
