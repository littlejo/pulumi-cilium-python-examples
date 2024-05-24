import pulumi
import base64
import json
import pulumi_eks as eks
import pulumi_aws as aws
import littlejo_cilium as cilium

config = pulumi.Config()
try:
    letter_azs = config.require("AZLetters").split(",")
except:
    letter_azs = "a,b".split(",")

region = aws.config.region
azs = [f"{region}{l}" for l in letter_azs ]

subnets = aws.ec2.get_subnets(
    filters=[
        aws.ec2.GetSubnetsFilterArgs(
            name="availability-zone",
            values=azs,
        )
    ]
)

# Create an EKS cluster
cluster = eks.Cluster(
    "my-cluster",
    name="pulumi-eks",
    subnet_ids=subnets.ids,
)

kubeconfig_b64 = cluster.kubeconfig.apply(
    lambda kc: base64.b64encode(json.dumps(kc).encode("utf-8")).decode("utf-8")
)

cilium_provider = cilium.Provider(f"ciliumProvider", config_content=kubeconfig_b64)

cilium = cilium.Install(
    "Install",
    version="1.15.5",
    opts=pulumi.ResourceOptions(depends_on=cluster, providers=[cilium_provider]),
)

# Export the cluster's kubeconfig and cluster name
pulumi.export("kubeconfig", cluster.kubeconfig)
pulumi.export("cluster_name", cluster.name)
