import pulumi
import littlejo_cilium as cilium

example_install = cilium.Install("exampleInstall",
    sets=[
        "ipam.mode=kubernetes",
        "ipam.operator.replicas=1",
        "tunnel=vxlan",
    ],
    version="1.14.5")

