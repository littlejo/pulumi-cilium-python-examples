import pulumi
import littlejo_cilium as cilium
from pulumi_command import local
import itertools

def cilium_clustermesh(i, kind):
    cmesh_provider = cilium.Provider(f"cmesh{i}", context=f"kind-cmesh{i}", opts=pulumi.ResourceOptions(depends_on=kind[i-1], parent=kind[i-1]))
    cmesh_cilium = cilium.Install(f"cmesh{i}Install",
        sets=[
            f"cluster.name=cmesh{i}",
            f"cluster.id={i}",
        ],
        version="1.15.5",
        opts=pulumi.ResourceOptions(depends_on=kind, providers=[cmesh_provider], parent=cmesh_provider),
    )
    return {
      "cmesh": cilium.Clustermesh(f"cmesh{i}Enable", service_type="NodePort", opts=pulumi.ResourceOptions(depends_on=[cmesh_cilium], providers=[cmesh_provider], parent=cmesh_cilium)),
      "provider": cmesh_provider,
    }

def combinlist(seq):
    return list(itertools.combinations(seq, 2))

def intersection(ll, la):
    res = []
    flat_res = []
    for l in ll:
        if list(set(l) & set(la)) == [] and list(set(flat_res) & set(l)) == []:
            res += [l]
            flat_res += [l[0], l[1]]

    return [la] + res

def combi_optimization(connections_list):
    intersect = []
    res = []
    flat_res = []

    for conn in connections_list_cst:
        if conn in connections_list:
           intersect = intersection(connections_list, conn)
           for i in intersect:
               connections_list.remove(i)
           res += [intersect]
           flat_res += intersect
    return (flat_res, res)

config = pulumi.Config()
try:
    cluster_number = int(config.require("clusterNumber"))
except:
    cluster_number = 4
kind_list = []
c = []
cmesh_connect = []
depends_on = []

cluster_ids = list(range(1, cluster_number+1))

connections_list = combinlist(cluster_ids)
connections_list_cst = connections_list[:]

flat_connections_list, connections_list = combi_optimization(connections_list)

for i in cluster_ids:
    kind_list += [local.Command(f"kindCluster-{i}",
        create=f"sed 's/NUMBER/{i}/g' kind.yaml.template > kind-{i}.yaml && kind create cluster --config kind-{i}.yaml --name cmesh{i}",
        delete=f"kind delete clusters cmesh{i} && rm kind-{i}.yaml",
    )]

for i in cluster_ids:
    c += [cilium_clustermesh(i, kind_list)]

k = 0
l = 0
null = []

for connections in connections_list:
    null += [local.Command(f"null-{l}", create=f"echo ''", opts=pulumi.ResourceOptions(depends_on=[a['cmesh'] for a in c]))]
    for conn in connections:
        i = conn[0]
        j = conn[1]
        cmesh_connect += [cilium.ClustermeshConnection(f"cmeshConnect-{i}-{j}", destination_context=f"kind-cmesh{i}", opts=pulumi.ResourceOptions(parent=null[l], depends_on=depends_on, providers=[c[j-1]['provider']]))]
        k += 1
    depends_on += cmesh_connect + null
    l += 1
