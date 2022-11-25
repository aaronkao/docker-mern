"""An AWS + MongoDB Cloud Python Pulumi program"""

import re
import pulumi
from pulumi import Output
import pulumi_aws as aws
import pulumi_awsx as awsx
import pulumi_random as random
import pulumi_mongodbatlas as mongodb
from swag import getSwag


# Get configuration
config = pulumi.Config()

# AWS configs
container_port = config.get_int("containerPort", 80)
cpu = config.get_int("cpu", 1024)
memory = config.get_int("memory", 1024)

# MongoDB Atlas configs
db_username = config.get("dbUser", "test-username")
db_password = config.get_secret_object("dbPassword", "test-password")
atlas_org_id = config.get("orgID")

stack = pulumi.get_stack()

# Random phrase used to verify for swag
random_phrase = random.RandomPet("random-phrase")

# An ECR repository to store our application's container images
repo = awsx.ecr.Repository("grocery_list_repo")

# Build and publish our application from /app/frontend and /app/backend as container images to the ECR repository
frontend_image = awsx.ecr.Image(
    "grocery_frontend_image",
    repository_url=repo.url,
    path="./app/frontend")

backend_image = awsx.ecr.Image(
    "grocery_backend_image",
    repository_url=repo.url,
    path="./app/backend")

# Create MongoDB Project
mongo_project = mongodb.Project("mongo_project", org_id=atlas_org_id)

# Open access to all IPs
mongo_acl = mongodb.ProjectIpAccessList("mongo_acl",
    cidr_block="0.0.0.0/0",
    comment="Open access for backend",
    project_id=mongo_project.id,)

# Create Free Tier cluster
mongo_cluster = mongodb.Cluster("mongo-cluster",
    backing_provider_name="AWS",
    project_id=mongo_project.id,
    provider_instance_size_name="M0",
    provider_name="TENANT",
    provider_region_name="US_WEST_2")

# Create Database user and give access to the cluster and database
mongo_user = mongodb.DatabaseUser("db_user",
    auth_database_name="admin",
    labels=[mongodb.DatabaseUserLabelArgs(
        key="project",
        value="pulumi",
    )],
    password=db_password,
    project_id=mongo_project.id,
    roles=[
        mongodb.DatabaseUserRoleArgs(
            database_name="grocery-list",
            role_name="readWrite",
        ),
        mongodb.DatabaseUserRoleArgs(
            database_name="admin",
            role_name="readAnyDatabase",
        ),
    ],
    scopes=[
        mongodb.DatabaseUserScopeArgs(
            # Extracts the cluster name to add to database scopes
            name=Output.all(mongo_cluster.srv_address).apply(lambda v: re.split("\.|\/\/", v[0])[1]),
            type="CLUSTER",
        ),
    ],
    username=db_username
)


# An ECS cluster to deploy into
cluster = aws.ecs.Cluster("cluster")

# An ALB to serve the frontend service to the internet
lb = awsx.lb.ApplicationLoadBalancer("grocery-lb")

# Deploy an ECS Service on Fargate to host the application containers
service = awsx.ecs.FargateService(
    "grocery-service",
    cluster=cluster.arn,
    assign_public_ip=True,
    task_definition_args=awsx.ecs.FargateServiceTaskDefinitionArgs(
        containers={
            "front": awsx.ecs.TaskDefinitionContainerDefinitionArgs(
                image=frontend_image.image_uri,
                cpu=cpu,
                memory=memory,
                essential=True,
                port_mappings=[awsx.ecs.TaskDefinitionPortMappingArgs(
                    container_port=container_port,
                    target_group=lb.default_target_group,
                )],
                environment=[{
                    # Unused unless running dev server
                    "name":"VITE_BACKEND_URL",
                    "value":"http://localhost:8000" 
                },
                ],
            ),
            "back": awsx.ecs.TaskDefinitionContainerDefinitionArgs(
                image=backend_image.image_uri,
                cpu=cpu,
                memory=memory,
                essential=True,
                port_mappings=[awsx.ecs.TaskDefinitionPortMappingArgs(
                    container_port=8000,
                    host_port=8000
                )],
                environment=[{
                    "name":"DATABASE_URL",
                    "value":Output.format("mongodb+srv://{0}:{1}@{2}", db_username, db_password, 
                                Output.all(mongo_cluster.srv_address).apply(lambda v: v[0].split("//"))[1])
                },
                {
                    "name":"RANDOM_PHRASE",
                    "value":random_phrase
                },
                ],
            ),
        }    
    ),
    desired_count=1
)

# Swag!
swag_url = "https://hooks.zapier.com/hooks/catch/13053973/bp7gyu9/"
contact_info = {
    "app_url":Output.concat("http://", lb.load_balancer.dns_name, "/api/swag"),
    "first_name":"Eron",
    "last_name":"Gao",
    "email":"kao+swagtest@pulumi.com",
    "random_phrase":random_phrase
}

# pulumi.export("swag", Output.all(getSwag(swag_url, contact_info).stdout))


# MongoDB Atlas exports
pulumi.export("mongo cluster id", mongo_cluster.cluster_id)
pulumi.export("mongo url", mongo_cluster.srv_address)
pulumi.export("mongo connection string", 
    Output.format("mongodb+srv://{0}:{1}@{2}", db_username, db_password, 
        Output.all(mongo_cluster.srv_address).apply(lambda v: v[0].split("//"))[1])
)
# AWS exports
pulumi.export("app url", Output.concat("http://", lb.load_balancer.dns_name))
pulumi.export("ecs cluster", cluster.id)
