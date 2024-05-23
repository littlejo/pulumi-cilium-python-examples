import pulumi
import littlejo_cilium as cilium
from pulumi_command import local

def cilium_clustermesh(i, kind):
    cmesh_provider = cilium.Provider(f"cmesh{i}", context=f"kind-cmesh{i}", opts=pulumi.ResourceOptions(depends_on=kind))
    cmesh_cilium = cilium.Install(f"cmesh{i}Install",
        sets=[
            f"cluster.name=cmesh{i}",
            f"cluster.id={i}",
            "ipam.mode=kubernetes",
        ],
        version="1.15.5",
        opts=pulumi.ResourceOptions(depends_on=kind, providers=[cmesh_provider]),
    )
    return {
      "cmesh": cilium.Clustermesh(f"cmesh{i}Enable", service_type="NodePort", opts=pulumi.ResourceOptions(depends_on=[cmesh_cilium], providers=[cmesh_provider])),
      "provider": cmesh_provider,
    }

def combinlist(seq, k):
    p = []
    i, imax = 0, 2**len(seq)-1
    while i<=imax:
        s = []
        j, jmax = 0, len(seq)-1
        while j<=jmax:
            if (i>>j)&1==1:
                s.append(seq[j])
            j += 1
        if len(s)==k:
            p.append(s)
        i += 1
    return p

kind_list = []
c = []
cmesh_connect = []

cluster_ids = list(range(1, 4))
combi = combinlist(cluster_ids, 2)

for i in cluster_ids:
    kind_list += [local.Command(f"kindCluster-{i}",
        create=f"sed 's/NUMBER/{i}/g' kind.yaml.template > kind-{i}.yaml && kind create cluster --config kind-{i}.yaml --name cmesh{i}",
        delete=f"kind delete clusters cmesh{i} && rm kind-{i}.yaml",
    )]

for i in cluster_ids:
    c += [cilium_clustermesh(i, kind_list)]


k = 0

for i, j in combi:
    depends_on = [c[j-1]['cmesh']] + cmesh_connect
    cmesh_connect += [cilium.ClustermeshConnection(f"cmeshConnect-{k}", destination_context=f"kind-cmesh{i}", opts=pulumi.ResourceOptions(depends_on=depends_on, providers=[c[j-1]['provider']]))]
    k += 1
