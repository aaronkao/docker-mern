# Docker MERN App Example
This is an example of a MERN stack deployed locally through Docker. 

![arch diagram](/architecture.png)

## Instructions
- Run Docker daemon
- Initialize Pulumi stack `pulumi stack init dev`
- Set App URL port `pulumi config set container_port 5173`
- Execute `pulumi up`