import pulumi
import base64
import json
import pulumi_awsx as awsx
import pulumi_aws as aws
import pulumi_eks as eks
from pulumi_command import local
import littlejo_cilium as cilium

def cilium_clustermesh(i, kind):
    kubeconfig_b64 = kind.kubeconfig.apply(
        lambda kc: base64.b64encode(json.dumps(kc).encode("utf-8")).decode("utf-8")
    )

    cmesh_provider = cilium.Provider(f"cilium-provider-{i}", config_content=kubeconfig_b64, opts=pulumi.ResourceOptions(depends_on=kind))
    cmesh_cilium = cilium.Install(f"cilium-install-{i}",
        sets=[
            f"cluster.name=cmesh{i}",
            f"cluster.id={i}",
        ],
        version="1.15.5",
        opts=pulumi.ResourceOptions(depends_on=kind, providers=[cmesh_provider]),
    )
    return {
      "cmesh": cilium.Clustermesh(f"cilium-cmesh-enable-{i}", service_type="LoadBalancer", opts=pulumi.ResourceOptions(depends_on=[cmesh_cilium], providers=[cmesh_provider])),
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

config = pulumi.Config()
try:
    cluster_number = int(config.require("clusterNumber"))
except:
    cluster_number = 2

cluster_ids = list(range(1, cluster_number+1))
cluster_name = "eks-cmesh"
region = aws.config.region
nodepool_number = 1

#default = aws.ec2.DefaultVpc("default", force_destroy=True)

tgw = aws.ec2transitgateway.TransitGateway("tgw-cmesh", description="Communication with VPCs for clustermesh cilium")
command = ""
eks_list = []
cmesh_list = []
cmesh_connect = []
k = 0
azs = [f"{region}a", f"{region}b"]

for cid in cluster_ids:
    vpc_mesh = awsx.ec2.Vpc(f"vpc-cmesh{cid}",
                             cidr_block=f"10.{cid}.0.0/16",
                             availability_zone_names=azs,
                             nat_gateways=awsx.ec2.NatGatewayConfigurationArgs(strategy=awsx.ec2.NatGatewayStrategy.SINGLE),
    )
    tgw_a = aws.ec2transitgateway.VpcAttachment(f"tgwa-cmesh-{cid}",
        subnet_ids=vpc_mesh.private_subnet_ids,
        transit_gateway_id=tgw.id,
        vpc_id=vpc_mesh.vpc_id)

    cluster_mesh = eks.Cluster(
        f"eks-cmesh{cid}",
        name=f"{cluster_name}{cid}",
        vpc_id=vpc_mesh.vpc_id,
        public_subnet_ids=vpc_mesh.public_subnet_ids,
        private_subnet_ids=vpc_mesh.private_subnet_ids,
        node_associate_public_ip_address=False,
        desired_capacity=nodepool_number
    )
    cilium_cmesh = cilium_clustermesh(cid, cluster_mesh)
    command += f"aws eks update-kubeconfig --name {cluster_name}{cid} --kubeconfig kubeconfig.yaml && "
    eks_list += [ cluster_mesh ]
    cmesh_list += [ cilium_cmesh["cmesh"] ]


kubeconfig_update = local.Command("kubeconfig",
        create=command[:-4],
        delete=f"rm -f kubeconfig.yaml",
        opts=pulumi.ResourceOptions(depends_on=cmesh_list)
    )

account_id = aws.get_caller_identity().account_id
context_arn_pre = f"arn:aws:eks:{region}:{account_id}:cluster"

combi = combinlist(cluster_ids, 2)

for i, j in combi:
    depends_on = cmesh_list + [kubeconfig_update] + cmesh_connect
    cmesh_provider = cilium.Provider(f"cilium-provider-cmesh-{k}", config_path="./kubeconfig.yaml", context=f"{context_arn_pre}/{cluster_name}{i}", opts=pulumi.ResourceOptions(depends_on=kubeconfig_update))
    cmesh_connect += [cilium.ClustermeshConnection(f"cilium-cmesh-connect-{k}", destination_context=f"{context_arn_pre}/{cluster_name}{j}",
                                                 opts=pulumi.ResourceOptions(depends_on=depends_on, providers=[cmesh_provider]))]
    k += 1
