"""
AWS CDK Elastic Beanstalk Stack
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import json
import logging
import hashlib
import os
from typing import Any, Dict, Optional

from aws_cdk import CfnOutput, Environment, Fn
from aws_cdk import aws_elasticbeanstalk as eb
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secrets
from constructs import Construct

from stacks.protected import NetworkProtectedStack
from stacks.settings import BeanstalkInstanceTypeSettings
from stacks.settings import BeanstalkLoadBalancerSchemeSettings
from stacks.settings import BeanstalkServerAmiSettings
from stacks.settings import BeanstalkStorageSize
from stacks.settings import DebugModeSettings
from stacks.settings import HttpsCertificateSettings
from stacks.settings import MaxNodesSettings
from stacks.settings import MinNodesSettings
from stacks.settings import RollingUpdateMaxBatchSizeSettings
from stacks.settings import RollingUpdateMinInstancesInServiceSettings
from stacks.settings import RollingUpdateRollingUpdateEnabledSettings
from stacks.settings import ServerKeyPairSettings
from stacks.settings import SharedCacheDatabaseSettings

logger: logging.RootLogger = logging.getLogger(__name__)


class BeanstalkStack(NetworkProtectedStack):
    """
    AWS Cloud Formation stack
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        application: str,
        network: str,
        description: str,
        database: str,
        environment: str,
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
        self._environment: str = environment
        self._database: str = database
        self._network: str = network

        # Imported values.
        self._eb_app_name: str = ""
        self._redis_host: str = ""
        self._reids_port: str = ""
        self._redis_db: str = self._get_redis_db()
        self._db_host: str = ""
        self._db_port: str = ""
        self._db_secret: str = ""
        self._os_host: str = ""
        self._ec2_role_name: str = ""
        self._ec2_profile_name: str = ""
        self._elb_role_name: str = ""
        self._ec2_sg_id: str = ""
        self._elb_sg_id: str = ""
        self._cdn_bucket_name: str = ""
        self._cdn_domain_name: str = ""
        self._deployments_bucket: str = ""

        # Stack resources.
        self._bucket: Optional[s3.Bucket] = None
        self._eb_env: Optional[eb.CfnEnvironment] = None
        self._version: Optional[eb.eb.CfnApplicationVersion] = None
        self._secret: Optional[secrets.Secret] = None

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
        if not self._database:
            raise AttributeError("Unknown database name!")
        self._eb_app_name: str = Fn.import_value(f"{self._application}::{self._network}::application::name")
        self._redis_host: str = Fn.import_value(f"{self._application}::{self._network}::cache::host")
        self._reids_port: str = Fn.import_value(f"{self._application}::{self._network}::cache::port")
        self._db_host: str = Fn.import_value(f"{self._application}::{self._network}::{self._database}::database::host")
        self._db_port: str = Fn.import_value(f"{self._application}::{self._network}::{self._database}::database::port")
        self._db_secret: str = Fn.import_value(
            f"{self._application}::{self._network}::{self._database}::database::secret"
        )
        self._os_host: str = Fn.import_value(f"{self._application}::{self._network}::opensearch::host")
        self._ec2_sg_id: str = Fn.import_value(f"{self._application}::{self._network}::application::ec2::sg::id")
        self._elb_sg_id: str = Fn.import_value(f"{self._application}::{self._network}::application::elb::sg::id")
        self._ec2_role_name: str = Fn.import_value(
            f"{self._application}::{self._network}::application::ec2::role::name"
        )
        self._elb_role_name: str = Fn.import_value(
            f"{self._application}::{self._network}::application::elb::role::name"
        )
        self._ec2_profile_name: str = Fn.import_value(
            f"{self._application}::{self._network}::application::ec2::profile::name"
        )
        self._cdn_bucket_name: str = Fn.import_value(
            f"{self._application}::{self._network}::bucket::name",
        )
        self._cdn_domain_name: str = Fn.import_value(
            f"{self._application}::{self._network}::cdn::domain",
        )
        self._deployments_bucket: str = Fn.import_value(
            f"{self._application}::deployments::bucket::name",
        )

    def deploy(self) -> None:
        """
        Creating resources in this stack.
        """
        logger.info("creating resources.")
        if not self._application:
            raise AttributeError("Unknown application name!")
        if not self._network:
            raise AttributeError("Unknown network name!")
        if not self._database:
            raise AttributeError("Unknown database name!")
        if not self._environment:
            raise AttributeError("Unknown environment name!")
        if not self.region:
            raise AttributeError("Unknown region name!")
        if not self._private_subnets:
            raise AttributeError("Private subnets not found!")
        if not self._public_subnets:
            raise AttributeError("Private subnets not found!")
        self._create_version()
        self._create_secret()
        self._create_bucket()
        self._create_env()

    def _get_redis_db(self) -> str:
        """
        Deciding what is the Redis DB ID.
        """
        logger.debug("Detecting Redis Database.")
        if not self._network:
            raise AttributeError("Network is missing")
        if not self._environment:
            raise AttributeError("Environment is missing")
        if SharedCacheDatabaseSettings.get(self._network):
            return '0'
        numeric: int = int(hashlib.sha256(self._environment.encode("utf-8")).hexdigest(), 16) % 10 ** 8
        return str(numeric)[-1]

    def _create_secret(self) -> None:
        """
        Creating a random secret.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_secretsmanager/Secret.html
        """
        logger.debug("Creating a random secret")
        self._secret: secrets.Secret = secrets.Secret(
            self,
            f"{self._application}-{self._network}-{self._environment}secret-key",
            secret_name=f"{self._application}-{self._network}-{self._environment}-secret-key",
            description="The secret key for this environment",
        )

    def _create_bucket(self) -> None:
        """
        Creating an AWS Bucket for the Frontend.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_s3/Bucket.html
        """
        logger.debug("Creating AWS S3 Bucket.")
        self._bucket: s3.Bucket = s3.Bucket(
            self,
            f"{self._application}-{self._network}-{self._environment}-frontend-bucket",
            bucket_name=f"{self._application}-{self._network}-{self._environment}-frontend-bucket",
            encryption=s3.BucketEncryption.KMS,
            access_control=s3.BucketAccessControl.PUBLIC_READ,
            website_error_document="404.html",
            website_index_document="index.html",
            public_read_access=True,
        )

    def export(self) -> None:
        """
        Exporting resources in this stack.
        """
        logger.info("Exporting resources.")
        CfnOutput(
            self,
            f"{self._application}::{self._network}::app::{self._environment}::url",
            export_name=f"{self._application}::{self._network}::app::{self._environment}::url",
            value=self._eb_env.attr_endpoint_url,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::frontend::{self._environment}::bucket::name",
            export_name=f"{self._application}::{self._network}::frontend::{self._environment}::bucket::name",
            value=self._bucket.bucket_name,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::app::{self._environment}::secret::name",
            export_name=f"{self._application}::{self._network}::app::{self._environment}::secret::name",
            value=self._secret.secret_name,
        )
        CfnOutput(
            self,
            f"{self._application}::{self._network}::app::{self._environment}::redis::db",
            export_name=f"{self._application}::{self._network}::app::{self._environment}::redis::db",
            value=self._redis_db,
        )

    def _create_version(self) -> None:
        """
        Creating a deployment version.
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_elasticbeanstalk/CfnApplicationVersion.html
        """
        logger.debug("Creation application version.")
        if not self._application:
            raise AttributeError("Missing application name!")
        if not self._environment:
            raise AttributeError("Missing environment name!")
        self._version: eb.CfnApplicationVersion = eb.CfnApplicationVersion(
            self,
            f"{self._application}-{self._environment}-application-version",
            application_name=self._eb_app_name,
            source_bundle=eb.CfnApplicationVersion.SourceBundleProperty(
                s3_bucket=self._deployments_bucket,
                s3_key=os.path.join(self._environment, "Dockerrun.aws.json"),
            ),
        )

    def _create_env(self) -> None:
        """
        Creating an AWS Elastic Beanstalk Application Environment
        https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_elasticbeanstalk/CfnEnvironment.html

        Supported platforms:
        https://docs.aws.amazon.com/elasticbeanstalk/latest/platforms/platforms-supported.html
        """
        logger.debug("Creating AWS Elastic Beanstalk Application Environment.")
        if not self._eb_app_name:
            raise AttributeError("Unknown AWS Elastic Beanstalk application name!")
        if not self._environment:
            raise AttributeError("Unknown AWS Elastic Beanstalk environment name!")
        self._eb_env: eb.CfnEnvironment = eb.CfnEnvironment(
            self,
            f"{self._application}-{self._network}-application-{self._environment}",
            application_name=self._eb_app_name,
            environment_name=f"{self._environment}-environment",
            solution_stack_name="64bit Amazon Linux 2 v3.4.17 running Docker",
            tier=eb.CfnEnvironment.TierProperty(
                name="WebServer",
                type="Standard",
            ),
            option_settings=[
                eb.CfnEnvironment.OptionSettingProperty(
                    namespace=namespace,
                    option_name=option,
                    value=value,
                )
                for namespace, options in self._get_options().items()
                for option, value in options.items()
                if option and value
            ],
        )

    def _get_options(self) -> Dict[str, Dict[str, Any]]:
        """
        Generates a dictionary of settings.
        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        options: Dict[str, Dict[str, Any]] = {
            "aws:elasticbeanstalk:application:environment": self._get_env_vars_options(),
            "aws:ec2:instances": self._get_ec2_instances_options(),
            "aws:autoscaling:updatepolicy:rollingupdate": self._get_rolling_update_options(),
            "aws:elasticbeanstalk:healthreporting:system:": self._get_health_options(),
            "aws:autoscaling:asg": self._get_autoscaling_options(),
            "aws:autoscaling:launchconfiguration": self._get_launch_options(),
            "aws:elasticbeanstalk:command": self._get_deployment_options(),
            "aws:elasticbeanstalk:application": self._get_application_options(),
            "aws:ec2:vpc": self._get_network_options(),
            "aws:elbv2:loadbalancer": self._get_elb_options(),
            "aws:elbv2:listener:default": self._get_elb_80_listener_options(),
            "aws:elbv2:listener:443": self._get_elb_443_listener_options(),
            "aws:elasticbeanstalk:environment": self._get_environment_options(),
            "aws:elasticbeanstalk:environment:process:default": self._get_process_options(),
        }
        options: Dict[str, str] = self._cast_to_string(options)
        logger.debug("Elastic Beanstalk options: %s", options)
        return options

    def _cast_to_string(self, value: object) -> object:
        """
        The configuration in Elastic Beanstalk must be a dictionary of strings.
        hits converts the options dictionary into a dictionary of plain strings.
        """
        if isinstance(value, dict):
            return {name: self._cast_to_string(item) for name, item in value.items()}
        elif isinstance(value, list):
            return json.dumps([self._cast_to_string(item) for item in value])
        elif isinstance(value, str):
            return value
        elif isinstance(value, bool):
            return json.dumps(value)
        elif isinstance(value, int):
            return json.dumps(value)
        raise TypeError(f"Invalid option: {value}")

    def _get_elb_443_listener_options(self) -> Dict[str, str]:
        """
        Generates a dictionary of settings for 'aws:elbv2:listener:443'.

        Configure additional listeners on an Application Load Balancer or a Network Load Balancer.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        return {
            "ListenerEnabled": True,
            "Protocol": "HTTPS",
            "SSLCertificateArns": self._get_certificate_arn(),
        }

    def _get_certificate_arn(self) -> str:
        """
        Generating an SSL certificate ARN.
        """
        logger.debug("Generating HTTPS SSL certificate ARN")
        return ':'.join([
            'arn',
            'aws',
            'acm',
            self.region,
            self.account,
            HttpsCertificateSettings.get(self._network),
        ])

    def _get_elb_80_listener_options(self) -> Dict[str, str]:
        """
        Generates a dictionary of settings for 'aws:elbv2:listener:default'.

        Configure the default listener (port 80) on an Application
        Load Balancer or a Network Load Balancer.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        return {
            "ListenerEnabled": True,
            "Protocol": "HTTP",
        }

    def _get_env_vars_options(self) -> Dict[str, str]:
        """
        Generates a dictionary of settings for 'aws:elasticbeanstalk:application:environment'.

        Configure environment properties for your application.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        return {
            "AWS_DEFAULT_REGION": self.region,
            "CDK_SECRET_KEY": self._secret.secret_name,
            "CDK_FRONTEND_BUCKET": self._bucket.bucket_name,
            "CDK_ACCOUNT_ID": self.account,
            "CDK_APP_ID": self._application,
            "CDK_ENV_ID": self._environment,
            "CDK_DEBUG": 'true' if DebugModeSettings.get(self._network) else 'false',
            "CDK_DATABASE_ID": self._database,
            "CDK_NETWORK_ID": self._network,
            "CDK_EB_APP_NAME": self._eb_app_name,
            "CDK_REDIS_HOST": self._redis_host,
            "CDK_REDIS_PORT": self._reids_port,
            "CDK_REDIS_DB": self._redis_db,
            "CDK_DB_HOST": self._db_host,
            "CDK_DB_PORT": self._db_port,
            "CDK_DB_SECRET": self._db_secret,
            "CDK_OPENSEARCH_HOST": self._os_host,
            "CDK_BUCKET_NAME": self._cdn_bucket_name,
            "CDK_DOMAIN_NAME": self._cdn_domain_name,
        }

    def _get_rolling_update_options(self) -> Dict[str, Any]:
        """
        Generates a dictionary of settings for 'aws:autoscaling:updatepolicy:rollingupdate'.

        Configure rolling updates your environment's Auto Scaling group.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        if RollingUpdateRollingUpdateEnabledSettings.get(self._network):
            return {
                "MaxBatchSize": RollingUpdateMaxBatchSizeSettings.get(self._network),
                "MinInstancesInService": RollingUpdateMinInstancesInServiceSettings.get(self._network),
                "RollingUpdateEnabled": True,
            }
        return {}

    def _get_ec2_instances_options(self) -> Dict[str, Any]:
        """
        Generates a dictionary of settings for 'aws:ec2:instances'.

        Configure your environment's instances, including Spot options.
        This namespace complements 'aws:autoscaling:launchconfiguration' and 'aws:autoscaling:asg'.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        return {
            "InstanceTypes": BeanstalkInstanceTypeSettings.get(self._network).to_string(),
            "SupportedArchitectures": "x86_64",
            "EnableSpot": True,
        }

    def _get_autoscaling_options(self) -> Dict[str, Any]:
        """
        Generates a dictionary of settings for 'aws:autoscaling:asg'.

        Configure your environment's Auto Scaling group.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        return {
            "MinSize": MinNodesSettings.get(self._environment),
            "MaxSize": MaxNodesSettings.get(self._environment),
        }

    def _get_launch_options(self) -> Dict[str, Any]:
        """
        Generates a dictionary of settings for 'aws:autoscaling:launchconfiguration'.

        Configure the Amazon Elastic Compute Cloud (Amazon EC2) instances for your environment.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        if not self._ec2_profile_name:
            raise RuntimeError("EC2 Profile not found!")
        return {
            "ImageId": BeanstalkServerAmiSettings.get(self._environment),
            "EC2KeyName": ServerKeyPairSettings.get(self._network),
            "IamInstanceProfile": self._ec2_profile_name,
            "RootVolumeSize": BeanstalkStorageSize.get(self._network),
            "SecurityGroups": [
                self._ec2_sg_id,
            ],
        }

    def _get_deployment_options(self) -> Dict[str, Any]:
        """
        Generates a dictionary of settings for 'aws:elasticbeanstalk:command'.

        Configure the deployment policy for your application code.
        For more information, see Deployment policies and settings.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        return {
            "DeploymentPolicy": "Rolling",
            "BatchSizeType": "Fixed",
            "BatchSize": 1,
            "Timeout": 3600,
            "IgnoreHealthCheck": False,
        }

    def _get_network_options(self) -> Dict[str, Any]:
        """
        Generates a dictionary of settings for 'aws:ec2:vpc'.

        Configure your environment to launch resources in a custom Amazon Virtual
        Private Cloud (Amazon VPC). If you don't configure settings in this namespace,
        Elastic Beanstalk launches resources in the default VPC.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        if not self._private_subnets:
            raise AttributeError("Failed to find private subnets!")
        if not self._public_subnets:
            raise AttributeError("Failed to find private subnets!")
        return {
            "VPCId": self._vpc.vpc_id,
            "Subnets": ",".join([subnet.subnet_id for subnet in self._private_subnets]),
            "ELBScheme": BeanstalkLoadBalancerSchemeSettings.get(self._network),
            "ELBSubnets": ",".join([subnet.subnet_id for subnet in self._public_subnets]),
        }

    def _get_application_options(self) -> Dict[str, Any]:
        """
        Generates a dictionary of settings for 'aws:elasticbeanstalk:application'.

        Configure a health check path for your application.
        For more information, see Basic health reporting.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        return {
            "Application Healthcheck URL": "/",
        }

    def _get_health_options(self) -> Dict[str, Any]:
        """
        Generates a dictionary of settings for 'aws:elasticbeanstalk:healthreporting:system'.

        Configure enhanced health reporting for your environment.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        return {
            "SystemType": "basic",
        }

    def _get_elb_options(self) -> Dict[str, Any]:
        """
        Generates a dictionary of settings for 'aws:elbv2:loadbalancer'.

        Configure an Application Load Balancer.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        return {
            "IdleTimeout": 300,
            "SecurityGroups": [
                self._elb_sg_id,
            ],
        }

    def _get_environment_options(self) -> Dict[str, Any]:
        """
        Generates a dictionary of settings for 'aws:elasticbeanstalk:environment'.

        Configure your environment's architecture and service role.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        if not self._elb_role_name:
            raise RuntimeError("ELB Role not found!")
        return {
            "EnvironmentType": "LoadBalanced",
            "ServiceRole": self._elb_role_name,
            "LoadBalancerType": "classic",
        }

    def _get_process_options(self) -> Dict[str, Any]:
        """
        Generates a dictionary of settings for 'aws:elasticbeanstalk:environment:process:default'.

        Configure your environment's default process.

        https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
        """
        return {
            "DeregistrationDelay": 20,
            "HealthCheckInterval": 60,
            "HealthCheckPath": "/",
            "HealthCheckTimeout": 30,
            "HealthyThresholdCount": 5,
            "UnhealthyThresholdCount": 5,
            "MatcherHTTPCode": "200,201,203,400,401,403",
            "Port": 80,
            "Protocol": "HTTP",
        }
