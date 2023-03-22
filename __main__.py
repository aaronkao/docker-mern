"""An local Docker MERN application Pulumi program"""

import pulumi
from pulumi import Output
import pulumi_docker as docker

# Get configuration
config = pulumi.Config()
container_port = config.get_int("containerPort", 5173)


stack = pulumi.get_stack()

# Create Docker Network
network = docker.Network("network", name=f"services-{stack}")

# Create Image from Dockerfile
shopping_app_image = docker.Image("shopping_image",
    build={
        "context": "./app",
        "args": {
            "BUILDKIT_INLINE_CACHE": "1"
        },
        "builder_version": "BuilderBuildKit", 
        "platform": "linux/amd64",
    },
    image_name="shopping-image:latest",
    skip_push=True
)

# Create Container from Image
shopping_app_container = docker.Container("shopping_app_container",
    image=shopping_app_image.image_name,
    ports=[{
        "internal": container_port,
        "external": container_port
    }],
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(
        name=network.name
    )],
    envs=[
        "DATABASE_URL=mongodb://host.docker.internal",
    ],
)


# Local MongoDB Community container image
mongo_image = docker.RemoteImage("mongo_image",
    name='mongo',
    keep_locally=True
)

# Create MongoDB container
mongo_local_container = docker.Container("mongo_local_container",
    image=mongo_image.latest,
    ports=[{
        "internal": 27017,
        "external": 27017
    }],
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(
        name=network.name
    )],
)

# Export the URL
pulumi.export("app url", Output.concat("http://localhost:", str(container_port)))

