"""
AWS CDK Application
https://docs.aws.amazon.com/cdk/v2/guide/cli.html
"""

import os
import sys
import logging

from typing import Dict

from aws_cdk import App
from aws_cdk import Environment

from stacks.registry import RegistryStack
from stacks.network import NetworkStack
from stacks.bastion import BastionStack
from stacks.search import OpensearchStack
from stacks.cache import CacheStack
from stacks.database import DatabaseStack
from stacks.security import SecurityStack
from stacks.application import ApplicationStack
from stacks.environment import BeanstalkStack
from stacks.media import MediaStack

# CDK application factory.
app: App = App()

# Reading parameters from the CLI.
settings: Dict[str, str] = {
    "profile": app.node.try_get_context("profile"),
    "application": app.node.try_get_context("application"),
    "database": app.node.try_get_context("database"),
    "network": app.node.try_get_context("network"),
    "environment": app.node.try_get_context("environment"),
    "env": Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    ),
}

# Validating whether the CLI parameters are OK.
if not settings['application']:
    raise ValueError("Missing 'application' parameter.")
if not settings['database']:
    raise ValueError("Missing 'database' parameter.")
if not settings['network']:
    raise ValueError("Missing 'network' parameter.")
if not settings['environment']:
    raise ValueError("Missing 'environment' parameter.")
if not settings['env']:
    raise ValueError("Missing 'env' parameter.")
if not os.environ["CDK_DEFAULT_ACCOUNT"]:
    raise OSError("Missing 'CDK_DEFAULT_ACCOUNT' environment variable")
if not os.environ["CDK_DEFAULT_REGION"]:
    raise OSError("Missing 'CDK_DEFAULT_REGION' environment variable")

# Setting logging configuration.
logger: logging.RootLogger = logging.getLogger(__name__)
if app.node.try_get_context("debug") == 'true':
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )
else:
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

# Deploying stacks.
logger.info("Starting CDK deployment: %s", settings)

# Deploying an AWS ECR repository
registry: RegistryStack = RegistryStack(
    app,
    construct_id="-".join([
        settings['application'],
        "registry",
        "stack",
    ]),
    description="AWS ECR resources",
    **settings,
)
registry.load()
registry.deploy()
registry.export()

# Deploying a shared AWS VPC.
# The network is shared across all the resources that have the same
# application and network name.
network: NetworkStack = NetworkStack(
    app,
    construct_id="-".join([
        settings['application'],
        settings['network'],
        "net",
        "stack",
    ]),
    description="AWS VPC resources",
    **settings,
)
network.load()
network.deploy()
network.export()

# Deploying a set of IAM Roles and Security Groups
# The IAM Roles are shared across all resources, for simplicity.
security: SecurityStack = SecurityStack(
    app,
    construct_id="-".join([
        settings['application'],
        settings['network'],
        "security",
        "stack",
    ]),
    description="AWS IAM Roles & Security Groups",
    **settings,
)
security.load()
security.deploy()
security.export()

# Deploying shared EC2 instances in the public network.
# The bastions are shared across all the resources that have the same
# application and network name.
bastion: BastionStack = BastionStack(
    app,
    construct_id="-".join([
        settings['application'],
        settings['network'],
        "bastion",
        "stack",
    ]),
    description="AWS EC2 resources",
    **settings,
)
bastion.load()
bastion.deploy()
bastion.export()

# Deploying a dedicated Elastic Beanstalk environment instance.
# The application is shared across all the resources that have the same
# application and network name.
application: ApplicationStack = ApplicationStack(
    app,
    construct_id="-".join([
        settings['application'],
        settings['network'],
        "app",
        "stack",
    ]),
    description="AWS Elastic Beanstalk application",
    **settings,
)
application.load()
application.deploy()
application.export()

# Deploying a dedicated Elastic Beanstalk environment instance.
# The application is shared across all the resources that have the same
# application and network name.
media: MediaStack = MediaStack(
    app,
    construct_id="-".join([
        settings['application'],
        settings['network'],
        "media",
        "stack",
    ]),
    description="AWS Bucket and Cloud Formation CDN",
    **settings,
)
media.load()
media.deploy()
media.export()

# Deploying a shared cache instance.
# The Redis cluster is shared across all the resources that have
# the same application and network name.
cache: CacheStack = CacheStack(
    app,
    construct_id="-".join([
        settings['application'],
        settings['network'],
        "redis",
        "stack",
    ]),
    description="AWS Elasticache cluster",
    **settings,
)
cache.load()
cache.deploy()
cache.export()

# Deploying a shared Opensearch cluster in the private network.
# The Opensearch cluster is shared across all the resources that have
# the same application and network name.
opensearch: OpensearchStack = OpensearchStack(
    app,
    construct_id="-".join([
        settings['application'],
        settings['network'],
        "os",
        "stack",
    ]),
    description="AWS Opensearch cluster",
    **settings,
)
opensearch.load()
opensearch.deploy()
opensearch.export()

# Deploying a dedicated database instance.
# The RDS instance is shared across all the resources that
# have the same application, network and database name.
database: DatabaseStack = DatabaseStack(
    app,
    construct_id="-".join([
        settings['application'],
        settings['network'],
        settings['database'],
        "database",
        "stack",
    ]),
    description="AWS RDS instance",
    **settings,
)
database.load()
database.deploy()
database.export()

# Deploying a dedicated Elastic Beanstalk environment instance.
# The beanstalk environment is always isolated from any other application.
environment: BeanstalkStack = BeanstalkStack(
    app,
    construct_id="-".join([
        settings['application'],
        settings['network'],
        settings['database'],
        settings['environment'],
        "environment",
        "stack",
    ]),
    description="AWS Elastic Beanstalk environment",
    **settings,
)
environment.load()
environment.deploy()
environment.export()

# Defining the dependencies between stacks.
# All resources are dependent on the AWS VPC & Subnets.
# Most of the resources are dependent on IAM roles & Security Groups.
# Finally, the AWS Elastic Beanstalk Envronments is dependent
# on all the resources having exported their outputs.
registry.add_dependency(network)
bastion.add_dependency(network)
security.add_dependency(network)
database.add_dependency(network)
media.add_dependency(network)
cache.add_dependency(network)
bastion.add_dependency(security)
opensearch.add_dependency(security)
application.add_dependency(registry)
environment.add_dependency(security)
environment.add_dependency(cache)
environment.add_dependency(database)
environment.add_dependency(opensearch)
environment.add_dependency(application)

# Generating AWS Cloud Formation template.
app.synth()
