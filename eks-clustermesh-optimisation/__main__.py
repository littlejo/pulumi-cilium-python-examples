#TODO
import pulumi
import pulumi_aws_native as aws_native
import pulumi_aws as aws_tf
from pulumi_command import local
import littlejo_cilium as cilium
import itertools
#import base64 #TOFIX

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

def get_assume_role_policy_document(service):
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": service},
            }
        ],
    }

def create_iam_role(name, trust_identity, managed_policies):
    managed_policy_arns = [f"arn:aws:iam::aws:policy/{p}" for p in managed_policies]
    role = aws_native.iam.Role(
        name,
        assume_role_policy_document=pulumi.Output.from_input(
            get_assume_role_policy_document(trust_identity)
        ),
        managed_policy_arns=managed_policy_arns,
    )
    return role

def create_sg(name, description, ingresses):
    sg = aws_native.ec2.SecurityGroup(
        name, group_description=description
    )
    egress = aws_native.ec2.SecurityGroupEgress(
        f"egress-{name}", group_id=sg.group_id, ip_protocol="-1", cidr_ip="0.0.0.0/0", opts=pulumi.ResourceOptions(parent=sg)
    )
    for i, ing in enumerate(ingresses):
        source_sg_id = ing.get("source_security_group_id")
        if source_sg_id == "self":
            source_sg_id = sg.group_id
        ingress = aws_native.ec2.SecurityGroupIngress(
            f"ingress-{name}-{i}",
            group_id=sg.group_id,
            ip_protocol=ing["ip_protocol"],
            cidr_ip=ing.get("cidr_ip"),
            from_port=ing["from_port"],
            to_port=ing["to_port"],
            source_security_group_id=source_sg_id,
            opts=pulumi.ResourceOptions(parent=sg),
        )
    return sg

def create_eks(name, role_arn, subnet_ids, sg_ids, version, ec2_role_arn, lt, i):
    eks_cluster = aws_native.eks.Cluster(
        name,
        name=name,
        role_arn=role_arn,
        resources_vpc_config=aws_tf.eks.ClusterVpcConfigArgs(
            subnet_ids=subnet_ids,
            security_group_ids=sg_ids,
            endpoint_public_access=True,
            public_access_cidrs=["0.0.0.0/0"],
        ),
        bootstrap_self_managed_addons=True,
        access_config={
                        "authentication_mode": "API",
                        "bootstrap_cluster_creator_admin_permissions": True, #TOFIX
                      },
        version=version,
    )
    cluster_name = eks_cluster.name

    #if ec2
    node_access = aws_native.eks.AccessEntry(f"node-{name}",
        cluster_name=name,
        principal_arn=ec2_role_arn,
        type="EC2_LINUX",
        opts=pulumi.ResourceOptions(parent=eks_cluster),
    )

    eks_dns_addon = aws_native.eks.Addon(f"dns-{name}",
        addon_name="coredns",
        cluster_name=cluster_name,
        opts=pulumi.ResourceOptions(parent=eks_cluster),
    )

    eks_kubeproxy_addon = aws_native.eks.Addon(f"kubeproxy-{name}",
        addon_name="kube-proxy",
        cluster_name=cluster_name,
        opts=pulumi.ResourceOptions(parent=eks_cluster),
    )

    #if ec2
    iam_profile = aws_native.iam.InstanceProfile(f"iamProfile-{i}",
        path="/",
        roles=[ec2_role.role_name],
        opts=pulumi.ResourceOptions(parent=ec2_role),
    )

    eks_name = eks_cluster.name.apply(lambda n: f"{n}")
    eks_ca = eks_cluster.certificate_authority_data.apply(lambda n: f"{n}")
    eks_ep = eks_cluster.endpoint.apply(lambda n: f"{n}")
    substituated={'EKS_NAME': eks_name, 'B64_CLUSTER_CA': eks_ca,'API_SERVER_URL': eks_ep, 'K8S_CLUSTER_DNS_IP': "10.100.0.10"}

    substitute = local.Command(f"substitute-{i}",
            create=f"envsubst < {template_name} | base64", #TOFIX
            environment=substituated,
            opts=pulumi.ResourceOptions(parent=eks_cluster),
        )
    ec2 = aws_native.ec2.Instance(f"ec2-eksCluster-{i}",
                                  instance_type=instance_type,
                                  image_id=ami.image_id,
                                  iam_instance_profile=iam_profile.instance_profile_name,
                                  security_group_ids=[ec2_sg.group_id],
                                  user_data=substitute.stdout,
                                  tags=[
                                    {
                                      "key": "Name",
                                      "value": f"ec2-eksCluster-{i}",
                                    },
                                    {
                                      "key": f"kubernetes.io/cluster/{name}",
                                      "value": "owned",
                                    },
                                    {
                                      "key": f"k8s.io/cluster/{name}",
                                      "value": "owned",
                                    },
                                  ],
                                  opts=pulumi.ResourceOptions(parent=substitute),
                                 )

    kubeconfig_update = local.Command(f"kubeconfig-{name}",
            create=f"aws eks update-kubeconfig --name {name} --kubeconfig kubeconfig-{name}.yaml",
            delete=f"rm -f kubeconfig-{name}.yaml",
            opts=pulumi.ResourceOptions(parent=ec2)
    )

    cilium_provider = cilium.Provider(f"cilium-provider-{name}", config_path=f"./kubeconfig-{name}.yaml", opts=pulumi.ResourceOptions(parent=kubeconfig_update))

    cilium_deploy = cilium.Install(f"cilium-install-{name}",
        sets=[
            f"cluster.name=cmesh{i}",
            f"cluster.id={i}",
            f"egressMasqueradeInterfaces={interfaces}",
            f"operator.replicas=1",
            f'ipam.mode=cluster-pool',
            f'routingMode=tunnel',
            'ipam.operator.clusterPoolIPv4PodCIDRList={10.%s.0.0/16}' % i,
        ],
        version="1.16.0",
        opts=pulumi.ResourceOptions(parent=cilium_provider, providers=[cilium_provider]),
    )

    cilium_cmesh = cilium.Clustermesh(f"cilium-cmesh-enable-{name}", service_type="NodePort", enable_kv_store_mesh=True, opts=pulumi.ResourceOptions(parent=cilium_deploy, providers=[cilium_provider])),
    #eks_vpccni_addon = aws_native.eks.Addon(f"vpccni-{name}",
    #    addon_name="vpc-cni",
    #    cluster_name=eks_cluster.name,
    #)
    #if nodegroup
    #eks_nodegroup = aws_native.eks.Nodegroup(f"eksNodegroup-{name}",
    #    cluster_name=cluster_name,
    #    node_role=ec2_role_arn,
    #    launch_template = {
    #      "name": lt.launch_template_name
    #    },
    #    taints=[{
    #        "effect": "NO_EXECUTE",
    #        "key": "node.cilium.io/agent-not-ready",
    #        "value": "true",
    #    }],
    #    scaling_config=aws_native.eks.NodegroupScalingConfigArgs(
    #        min_size=1,
    #        desired_size=1,
    #        max_size=1,
    #    ),
    #    subnets=subnet_ids,
    #    opts=pulumi.ResourceOptions(parent=eks_cluster)
    #    )
    return eks_cluster, cilium_cmesh

config = pulumi.Config()
try:
    cluster_number = int(config.require("clusterNumber"))
except:
    cluster_number = 4
cluster_ids = list(range(1, cluster_number+1))

region = aws_tf.config.region
azs = [f"{region}a", f"{region}b"]

subnets = aws_tf.ec2.get_subnets(
    filters=[
        aws_tf.ec2.GetSubnetsFilterArgs(
            name="availability-zone",
            values=azs,
        ),
    ]
)

kubernetes_version = "1.30"
arch = "arm"

if arch == "arm":
    ami_name_regex = f"^amazon-eks-node-al2023-arm64-standard-{kubernetes_version}-v20.*"
    instance_type = "t4g.medium"
    template_name = "userdata/template-arm"
    interfaces = "ens+"
else:
    ami_name_regex = f"^amazon-eks-node-{kubernetes_version}-v202.*"
    instance_type = "t3.micro"
    template_name = "userdata/template"
    interfaces = "eth0"

ami = aws_tf.ec2.get_ami(
    most_recent=True,
    name_regex=ami_name_regex
    )

eks_role = create_iam_role("eksRole", "eks.amazonaws.com", ["AmazonEKSClusterPolicy"])
ec2_role = create_iam_role("ec2Role", "ec2.amazonaws.com", ["AmazonEC2ContainerRegistryReadOnly", "AmazonEKS_CNI_Policy", "AmazonEKSWorkerNodePolicy"])

eks_sg = create_sg("eks_sg", "EKS control plane security group", [{"ip_protocol": "tcp", "cidr_ip": "0.0.0.0/0", "from_port": 443, "to_port": 443}])
ec2_sg = create_sg("ec2_sg", "EKS nodes security group", [
                                                          {"ip_protocol": "-1", "source_security_group_id": "self", "from_port": -1, "to_port": -1},
                                                          {"ip_protocol": "-1", "source_security_group_id": eks_sg.group_id, "from_port": -1, "to_port": -1},
                                                          {"ip_protocol": "tcp", "cidr_ip": "0.0.0.0/0", "from_port": 30000, "to_port": 32767},
                                                          {"ip_protocol": "icmp", "cidr_ip": "0.0.0.0/0", "from_port": -1, "to_port": -1},
                                                         ])

lt = aws_native.ec2.LaunchTemplate("lt-eks",
                   launch_template_name="lt-eks",
                   launch_template_data={
                     "security_group_ids": [ec2_sg.group_id]
                   }
     )

command = ""
cmesh_list = []
for i in cluster_ids:
    eks_cluster, cilium_cmesh = create_eks(f"eksCluster-{i}", eks_role.arn, subnets.ids, [eks_sg.group_id], kubernetes_version, ec2_role.arn, lt, i)
    cmesh_list += cilium_cmesh
    command += f"aws eks update-kubeconfig --name eksCluster-{i} --kubeconfig kubeconfig.yaml && "

kubeconfig_update = local.Command("kubeconfig",
        create=command[:-4],
        delete=f"rm -f kubeconfig.yaml",
        opts=pulumi.ResourceOptions(depends_on=cmesh_list)
    )

account_id = aws_tf.get_caller_identity().account_id
context_arn_pre = f"arn:aws:eks:{region}:{account_id}:cluster"

k = 0
l = 0
cmesh_connect = []
depends_on = []
null = []

connections_list = combinlist(cluster_ids)
connections_list_cst = connections_list[:]

flat_connections_list, connections_list = combi_optimization(connections_list)

for connections in connections_list:
    null += [local.Command(f"null-{l}", create=f"echo ''", opts=pulumi.ResourceOptions(depends_on=cmesh_list))]
    for conn in connections:
        i = conn[0]
        j = conn[1]
        cmesh_provider = cilium.Provider(f"cilium-provider-cmesh-{k}", config_path="./kubeconfig.yaml", context=f"{context_arn_pre}/eksCluster-{j}", opts=pulumi.ResourceOptions(depends_on=kubeconfig_update, parent=null[l]))
        cmesh_connect += [cilium.ClustermeshConnection(f"cmeshConnect-{i}-{j}", destination_context=f"{context_arn_pre}/eksCluster-{i}", opts=pulumi.ResourceOptions(parent=cmesh_provider, depends_on=depends_on, providers=[cmesh_provider]))]
        k += 1
    depends_on += cmesh_connect + null
    l += 1
