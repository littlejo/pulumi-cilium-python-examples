import pulumi
import littlejo_cilium as cilium

kind = local.Command("kindCluster",
    create="kind create cluster --config kind.yaml --name pulumi"
)

example_install = cilium.Install("exampleInstall",
    sets=[
        "ipam.mode=kubernetes",
        "ipam.operator.replicas=1",
        "tunnel=vxlan",
    ],
    version="1.14.5",
    opts=pulumi.ResourceOptions(depends_on=[kind]),
)

