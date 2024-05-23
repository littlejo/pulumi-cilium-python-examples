import pulumi
import littlejo_cilium as cilium
from pulumi_command import local

kind = local.Command("kindCluster",
    create="kind create cluster --config kind.yaml --name cmesh1"
)

kind2 = local.Command("kindCluster2",
    create="kind create cluster --config kind-2.yaml --name cmesh2"
)

cmesh1_provider = cilium.Provider("cmesh1", context="kind-cmesh1")
cmesh2_provider = cilium.Provider("cmesh2", context="kind-cmesh2")

cmesh1_cilium = cilium.Install("cmesh1Install",
    sets=[
        "cluster.name=cmesh1",
        "cluster.id=1",
        "ipam.mode=kubernetes",
    ],
    version="1.15.5",
    opts=pulumi.ResourceOptions(depends_on=[kind], providers=[cmesh1_provider]),
)

cmesh2_cilium = cilium.Install("cmesh2Install",
    sets=[
        "cluster.name=cmesh2",
        "cluster.id=2",
        "ipam.mode=kubernetes",
    ],
    version="1.15.5",
    opts=pulumi.ResourceOptions(depends_on=[kind2], providers=[cmesh2_provider]),
)

cmesh1_cmeshenable = cilium.Clustermesh("cmesh1Enable", service_type="NodePort", opts=pulumi.ResourceOptions(depends_on=[cmesh1_cilium], providers=[cmesh1_provider]))
cmesh2_cmeshenable = cilium.Clustermesh("cmesh2Enable", service_type="NodePort", opts=pulumi.ResourceOptions(depends_on=[cmesh2_cilium], providers=[cmesh2_provider]))

cilium.ClustermeshConnection("cmeshConnect", destination_context="kind-cmesh2", opts=pulumi.ResourceOptions(depends_on=[cmesh1_cmeshenable], providers=[cmesh1_provider]))
