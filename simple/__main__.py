import pulumi
import littlejo_cilium as cilium

example_install = cilium.Install("exampleInstall",
    sets=[
        "cluster.name=clustermesh1",
        "cluster.id=1",
        "ipam.mode=kubernetes",
    ],
    version="1.14.5")

