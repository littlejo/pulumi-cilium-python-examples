import pulumi
import littlejo_cilium as cilium
from pulumi_command import local

def cilium_clustermesh(i, kind):
    cmesh_provider = cilium.Provider(f"cmesh{i}", context=f"kind-cmesh{i}", opts=pulumi.ResourceOptions(parent=kind[i]))
    cmesh_cilium = cilium.Install(f"cmesh{i}Install",
        sets=[
            f"cluster.name=cmesh{i}",
            f"cluster.id={i+1}",
            "ipam.mode=kubernetes",
        ],
        version="1.15.5",
        opts=pulumi.ResourceOptions(providers=[cmesh_provider], parent=cmesh_provider),
    )
    return {
      "cmesh": cilium.Clustermesh(f"cmesh{i}Enable", service_type="NodePort", opts=pulumi.ResourceOptions(depends_on=[cmesh_cilium], providers=[cmesh_provider], parent=cmesh_cilium)),
      "provider": cmesh_provider,
    }

config = pulumi.Config()
try:
    cluster_number = int(config.require("clusterNumber"))
except:
    cluster_number = 3
kind_list = []
c = []
cmesh_connect = []

cluster_ids = list(range(cluster_number))

for i in cluster_ids:
    kind_list += [local.Command(f"kindCluster-{i}",
        create=f"sed 's/NUMBER/{i}/g' kind.yaml.template > kind-{i}.yaml && kind create cluster --config kind-{i}.yaml --name cmesh{i}",
        delete=f"kind delete clusters cmesh{i} && rm kind-{i}.yaml",
    )]

for i in cluster_ids:
    c += [cilium_clustermesh(i, kind_list)]

cmesh_connect = cilium.ClustermeshConnection(f"cmeshConnect",
                                              destination_contexts=[f"kind-cmesh{i}" for i in cluster_ids if i !=0],
                                              connection_mode="mesh",
                                              parallel=3,
                                              opts=pulumi.ResourceOptions(depends_on=[c[i]["cmesh"] for i in cluster_ids], providers=[c[0]['provider']]))
