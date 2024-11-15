import pulumi
import pulumi_aws as aws_tf
from pulumi_command import local
import littlejo_cilium as cilium
import ipaddress

def get_userdata(eks_name, api_server_url, ca, cidr):
    combined = pulumi.Output.all(eks_name, api_server_url, ca, cidr)
    return combined.apply(lambda vars: f"""Content-Type: multipart/mixed; boundary="MIMEBOUNDARY"
MIME-Version: 1.0

--MIMEBOUNDARY
Content-Transfer-Encoding: 7bit
Content-Type: application/node.eks.aws
Mime-Version: 1.0

---
apiVersion: node.eks.aws/v1alpha1
kind: NodeConfig
spec:
  cluster:
    name: {vars[0]}
    apiServerEndpoint: {vars[1]}
    certificateAuthority: {vars[2]}
    cidr: {vars[3]}

--MIMEBOUNDARY--
""")

def tags_format(tags_dict):
    return [ {'key': k, 'value': v} for k, v in tags_dict.items() ]

class VPC:
   def __init__(self, name, cidr="10.0.0.0/16", azs=[], parent=None):
       self.name = name
       self.cidr = cidr
       self.parent = parent
       self.create_vpc()
       new_prefix = int(cidr.split("/")[1])+2
       self.azs = azs
       self.subnet_cidr = list(ipaddress.ip_network(cidr).subnets(new_prefix=new_prefix))

   def create_vpc(self):
       tags = {
         "Name": self.name
       }
       self.vpc = aws_tf.ec2.Vpc(
           f"vpc-{self.name}",
           cidr_block=self.cidr,
           enable_dns_hostnames=True,
           enable_dns_support=True,
           opts=pulumi.ResourceOptions(parent=self.parent),
           tags=tags
       )

   def get_vpc_id(self):
       return self.vpc.id

   def get_subnet_ids(self):
       return [self.subnets["subnet-private-0"].id, self.subnets["subnet-private-1"].id]

   def create_subnets(self):
       subnets_map = {
         f"subnet-public-0": 0,
         f"subnet-public-1": 1,
         f"subnet-private-0": 2,
         f"subnet-private-1": 3,
       }
       self.subnets = {}

       for name, index in subnets_map.items():
           self.subnets[name] = aws_tf.ec2.Subnet(
               name + f"-{self.name}",
               vpc_id=self.vpc.id,
               cidr_block=self.subnet_cidr[index].with_prefixlen,
               availability_zone=self.azs[index % 2],
               opts=pulumi.ResourceOptions(parent=self.vpc),
               map_public_ip_on_launch=(name.startswith("subnet-public-")),
               tags={"Name": name + f"-{self.name}"},
           )

   def create_nat_gateway(self):
       tags = {
         "Name": self.name
       }
       nat_eip = aws_tf.ec2.Eip("vpc-eip",
           opts = pulumi.ResourceOptions(parent=self.parent),
	   tags = tags,
       )
       self.nat_gw = aws_tf.ec2.NatGateway("vpc-nat-gw",
           allocation_id=nat_eip.id,
           subnet_id=self.subnets["subnet-public-0"],
	   tags = tags,
           opts = pulumi.ResourceOptions(parent=nat_eip)
       )

   def create_internet_gateway(self):
       self.igw = aws_tf.ec2.InternetGateway(f"vpc-igw-{self.name}",
                                                vpc_id=self.vpc.id,
                                                opts=pulumi.ResourceOptions(parent=self.parent))

   def create_route_table(self, table_type):
       tags = {
         "Name": f"vpc-rt-{table_type}-{self.name}",
       }

       nat_gateway_id = self.nat_gw.id if table_type == "private" else None
       gateway_id = self.igw.id if table_type == "public" else None

       rt = aws_tf.ec2.RouteTable(f"vpc-rt-{table_type}-{self.name}",
                                        vpc_id=self.vpc.id,
                                        opts=pulumi.ResourceOptions(parent=self.vpc),
                                        tags=tags,
                )

       aws_tf.ec2.Route(f"vpc-rt-r-{table_type}-{self.name}",
                                 route_table_id=rt.id,
                                 destination_cidr_block="0.0.0.0/0",
                                 gateway_id=gateway_id,
                                 nat_gateway_id=nat_gateway_id,
                                 opts=pulumi.ResourceOptions(parent=rt)
       )

       aws_tf.ec2.RouteTableAssociation(f"vpc-rt-assoc-{table_type}-{self.name}-1",
                                        subnet_id=self.subnets[f"subnet-{table_type}-0"],
                                        route_table_id=rt.id,
                                        opts=pulumi.ResourceOptions(parent=rt)
       )

       aws_tf.ec2.RouteTableAssociation(f"vpc-rt-assoc-{table_type}-{self.name}-2",
                                        subnet_id=self.subnets[f"subnet-{table_type}-1"],
                                        route_table_id=rt.id,
                                        opts=pulumi.ResourceOptions(parent=rt)
       )

   def create_route_tables(self):
       self.create_route_table("public")
       self.create_route_table("private")


class SecurityGroup:
   def __init__(self, name, vpc_id="", description="", ingresses=[], egresses=[], parent=None):
       self.name = name
       self.vpc_id = vpc_id
       self.description = description
       self.ingresses = ingresses
       self.egresses = egresses
       self.parent = parent
       self.create_sg()

   def create_sg(self):
       self.sg = aws_tf.ec2.SecurityGroup(
           f"sg-{self.name}",
           vpc_id=self.vpc_id,
           name=self.name,
           description=self.description,
           opts=pulumi.ResourceOptions(parent=self.parent),
       )

       self.create_egresses()
       self.create_ingresses()

   def create_egresses(self):
       if len(self.egresses) == 0:
           egress = aws_tf.vpc.SecurityGroupEgressRule(
               f"sg-egress-{self.name}", security_group_id=self.sg.id, ip_protocol="-1", cidr_ipv4="0.0.0.0/0", opts=pulumi.ResourceOptions(parent=self.sg)
           )
       else:
           pass #TODO

   def create_ingresses(self):
       for i, ing in enumerate(self.ingresses):
           source_sg_id = ing.get("source_security_group_id")
           if source_sg_id == "self":
               source_sg_id = self.sg.id
           ingress = aws_tf.vpc.SecurityGroupIngressRule(
               f"sg-ingress-{self.name}-{i}",
               security_group_id=self.sg.id,
               ip_protocol=ing["ip_protocol"],
               cidr_ipv4=ing.get("cidr_ip"),
               from_port=ing["from_port"],
               to_port=ing["to_port"],
               referenced_security_group_id=source_sg_id,
               opts=pulumi.ResourceOptions(parent=self.sg),
           )

   def get_id(self):
       return self.sg.id

class IAMRole:
   def __init__(self, name, trust_identity="", managed_policies=[], parent=None):
      self.managed_policy_arns = [f"arn:aws:iam::aws:policy/{p}" for p in managed_policies]
      self.service = trust_identity
      self.parent = parent
      self.name = name
      self.create_role()

   def create_role(self):
      self.role = aws_tf.iam.Role(
          f"iam-role-{self.name}",
          name=self.name,
          assume_role_policy=pulumi.Output.from_input(
              self.get_assume_role_policy_document()
          ),
          managed_policy_arns=self.managed_policy_arns,
          opts=pulumi.ResourceOptions(parent=self.parent),
      )

   def create_profile(self):
      self.profile = aws_tf.iam.InstanceProfile(f"iam-profile-{self.name}",
          path="/",
          role=self.role.name,
          opts=pulumi.ResourceOptions(parent=self.role),
      )

   def get_assume_role_policy_document(self):
       return {
           "Version": "2012-10-17",
           "Statement": [
               {
                   "Action": "sts:AssumeRole",
                   "Effect": "Allow",
                   "Principal": {"Service": self.service},
               }
           ],
       }

   def get_arn(self):
       return self.role.arn

   def get_profile_name(self):
       return self.profile.name

class Cilium:
   def __init__(self, k8s_name, config_path=None, parent=None, depends_on=[], context=None):
       self.k8s_name = k8s_name
       self.provider = cilium.Provider(f"cilium-provider-{k8s_name}", config_path=config_path, context=context, opts=pulumi.ResourceOptions(parent=parent, depends_on=depends_on))

   def deploy(self, version, sets=None):
       self.deploy = cilium.Install(f"cilium-install-{self.k8s_name}",
         sets=sets,
         version=version,
         opts=pulumi.ResourceOptions(parent=self.provider, providers=[self.provider]),
      )

   def cmesh_enable(self, service_type):
       self.cmesh = cilium.Clustermesh(f"cilium-cmesh-enable-{self.k8s_name}", service_type=service_type, opts=pulumi.ResourceOptions(parent=self.deploy, providers=[self.provider])),

   def cmesh_connection(self, name, destination_contexts=None, connection_mode="mesh", parallel=2, depends_on=[]):
       self.cmesh_connect = cilium.ClustermeshConnection(f"cilium-cmesh-connect-{name}",
                                                         destination_contexts=destination_contexts,
                                                         connection_mode=connection_mode,
                                                         parallel=parallel,
                                                         opts=pulumi.ResourceOptions(parent=self.provider,
                                                                                     depends_on=depends_on,
                                                                                     providers=[self.provider])
                                                        )
   def get_cmesh_enable(self):
       return self.cmesh

class EKS:
   def __init__(self, name, id="", role_arn="", subnet_ids=[], sg_ids=[], version="1.30", ec2_role_arn="", ec2_sg_ids=[], ec2_profile_name="", parent=None):
       self.name = name
       self.id = id
       self.role_arn = role_arn
       self.subnet_ids = subnet_ids
       self.sg_ids = sg_ids
       self.version = version
       self.parent = parent
       self.create_eks()
       self.ec2 = {
         "role_arn": ec2_role_arn,
         "sg_ids": ec2_sg_ids,
         "profile_name": ec2_profile_name,
       }

   def create_eks(self):
       self.cluster = aws_tf.eks.Cluster(
           f"eks-cp-{self.name}",
           name=self.name,
           role_arn=self.role_arn,
           vpc_config=aws_tf.eks.ClusterVpcConfigArgs(
               subnet_ids=self.subnet_ids,
               security_group_ids=self.sg_ids,
               endpoint_public_access=True,
               endpoint_private_access=True,
               public_access_cidrs=["0.0.0.0/0"],
           ),
           bootstrap_self_managed_addons=True,
           access_config={
                           "authentication_mode": "API",
                           "bootstrap_cluster_creator_admin_permissions": True, #TOFIX
                         },
           version=self.version,
           opts=pulumi.ResourceOptions(parent=self.parent),
       )

   def create_ec2(self):
       tags_dict = {
                     'Name': f"ec2-{self.name}",
                   }

       user_data = get_userdata(self.cluster.name, self.cluster.endpoint, self.cluster.certificate_authority["data"], self.cluster.kubernetes_network_config.service_ipv4_cidr)
       self.ec2 = aws_tf.ec2.Instance(f"ec2-{self.name}",
                                     instance_type=instance_type,
                                     subnet_id=self.subnet_ids[self.id % 2],
                                     ami=ami.image_id,
                                     iam_instance_profile=self.ec2["profile_name"],
                                     vpc_security_group_ids=self.ec2["sg_ids"],
                                     user_data=user_data,
                                     tags=tags_dict,
                                     opts=pulumi.ResourceOptions(parent=self.cluster),
                                    )

   def create_kubeconfig_eks(self):
       self.kubeconfig_eks = local.Command(f"cmd-kubeconfig-{self.name}",
               create=f"aws eks update-kubeconfig --name {self.name} --kubeconfig kubeconfig-{self.name}.yaml",
               delete=f"rm -f kubeconfig-{self.name}.yaml",
               opts=pulumi.ResourceOptions(parent=self.cluster)
       )

   def create_kubeconfig_sa(self):
       self.kubeconfig = f"kubeconfig-sa-{self.id}"
       #auth = aws_tf.eks.get_cluster_auth(name=self.cluster.cluster_id)
       self.kubeconfig_sa = local.Command(f"cmd-kubeconfig-sa-{self.name}",
               create=f"bash helper/creation-kubeconfig.sh {self.kubeconfig}",
               delete=f"rm -f {self.kubeconfig}",
               environment={
                             "AWS_DEFAULT_REGION": region,
                             "KUBECONFIG": f"kubeconfig-{self.name}.yaml",
                             "serviceaccount": f"admin-{self.id}",
                             "cluster": self.name,
                             "ca": self.cluster.certificate_authority["data"],
                             "server": self.cluster.endpoint,
                             "account": self.cluster.arn,
                             "crt_cilium": ca_crt,
                             "key_cilium": ca_key,

       #                      "token": auth.token,
                           },
               opts=pulumi.ResourceOptions(parent=self.cluster)
       )

   def get_ec2(self):
       return self.ec2

   def get_kubeconfig(self):
       return self.kubeconfig

   def get_kubeconfig_sa(self):
       return self.kubeconfig_sa

   def get_name(self):
       return self.cluster.name

   def add_node_access(self):
       aws_tf.eks.AccessEntry(f"eks-access-entry-ec2-{self.name}",
           cluster_name=self.name,
           principal_arn=self.ec2["role_arn"],
           type="EC2_LINUX",
           opts=pulumi.ResourceOptions(parent=self.cluster),
       )

   def add_dns_addon(self):
       aws_tf.eks.Addon(f"eks-addon-dns-{self.name}",
           addon_name="coredns",
           cluster_name=self.name,
           opts=pulumi.ResourceOptions(parent=self.cilium.deploy),
       )

   def add_kubeproxy_addon(self):
       aws_tf.eks.Addon(f"eks-addon-kubeproxy-{self.name}",
           addon_name="kube-proxy",
           cluster_name=self.name,
           opts=pulumi.ResourceOptions(parent=self.cluster),
       )

   def add_cilium(self, config_path="", parent=None, depends_on=[], version="1.16.0", sets=[], cmesh_service=""):
       self.cilium = Cilium(self.name, config_path=self.kubeconfig, parent=self.kubeconfig_sa, depends_on=depends_on)
       self.cilium.deploy(version, sets=sets)
       if cmesh_service != "":
           self.cilium.cmesh_enable(service_type=cmesh_service)

   def get_cilium_cmesh(self):
       return self.cilium.get_cmesh_enable()

def create_vpc(null_vpc, cidr=""):
    vpc = VPC(f"private-{region}-{pool_id}", azs=azs, parent=null_vpc, cidr=cidr)
    vpc.create_subnets()
    vpc.create_internet_gateway()
    vpc.create_nat_gateway()
    vpc.create_route_tables()
    return vpc

def create_roles(null_sec):
    eks_role = IAMRole(f"eks-cp-{region}-{pool_id}", trust_identity="eks.amazonaws.com", managed_policies=["AmazonEKSClusterPolicy"], parent=null_sec)
    ec2_role = IAMRole(f"eks-ec2-{region}-{pool_id}", trust_identity="ec2.amazonaws.com", managed_policies=["AmazonEC2ContainerRegistryReadOnly", "AmazonEKS_CNI_Policy", "AmazonEKSWorkerNodePolicy"], parent=null_sec)
    ec2_role.create_profile()
    return eks_role, ec2_role

def create_sg(null_sec):
    eks_sg = SecurityGroup(f"eks-cp-{region}", vpc_id=vpc.get_vpc_id(), description="EKS control plane security group", ingresses=[{"ip_protocol": "tcp", "cidr_ip": "0.0.0.0/0", "from_port": 443, "to_port": 443}], parent=null_sec)
    ec2_sg = SecurityGroup(f"eks-worker-{region}", vpc_id=vpc.get_vpc_id(), description="EKS nodes security group", parent=null_sec, ingresses= [
                                                              {"ip_protocol": "-1", "source_security_group_id": "self", "from_port": -1, "to_port": -1},
                                                              {"ip_protocol": "-1", "source_security_group_id": eks_sg.get_id(), "from_port": -1, "to_port": -1},
                                                              {"ip_protocol": "tcp", "cidr_ip": "0.0.0.0/0", "from_port": 30000, "to_port": 32767},
                                                              {"ip_protocol": "icmp", "cidr_ip": "0.0.0.0/0", "from_port": -1, "to_port": -1},
                                                              {"ip_protocol": "-1", "cidr_ip": "172.31.0.0/16", "from_port": -1, "to_port": -1},
                                                             ])
    return eks_sg, ec2_sg

def create_eks(null_eks, role_arn, subnet_ids, sg_ids, ec2_role_arn, ec2_sg_ids, ec2_profile_name, pool_id):
    cmesh_list = []
    kubeconfigs = []
    for i in cluster_ids:
        cilium_sets = [
                             f"cluster.name=cmesh{i+1}",
                             f"cluster.id={i+1}",
                             f"egressMasqueradeInterfaces={interfaces}",
                             f"operator.replicas=1",
                             f'ipam.mode=cluster-pool',
                             f'routingMode=tunnel',
                             f'clustermesh.maxConnectedClusters=511',
                             'ipam.operator.clusterPoolIPv4PodCIDRList={10.%s.%s.0/24}' % (pool_id, i),
        ]
        eks_cluster = EKS(f"eksCluster-{i}",
                          id=i,
                          role_arn=role_arn,
                          subnet_ids=subnet_ids,
                          sg_ids=sg_ids,
                          version=kubernetes_version,
                          ec2_role_arn=ec2_role_arn,
                          ec2_sg_ids=ec2_sg_ids,
                          ec2_profile_name=ec2_profile_name,
                          parent=null_eks)
        eks_cluster.add_node_access()
        eks_cluster.add_kubeproxy_addon()
        eks_cluster.create_kubeconfig_sa()
        eks_cluster.create_ec2()
        eks_cluster.add_cilium(config_path=eks_cluster.get_kubeconfig(), version="1.16.3", parent=eks_cluster.get_kubeconfig_sa(), sets=cilium_sets, cmesh_service="NodePort", depends_on=[eks_cluster.get_ec2()])
        eks_cluster.add_dns_addon()
        cmesh_list += eks_cluster.get_cilium_cmesh()
        kubeconfigs += [ eks_cluster.get_kubeconfig() ]

    kubeconfig_global = local.Command("cmd-kubeconfig-connect",
            create="kubectl config view --raw | tee ./kubeconfig.yaml",
            delete=f"rm -f kubeconfig.yaml",
            environment={"KUBECONFIG": ":".join(kubeconfigs)},
            opts=pulumi.ResourceOptions(depends_on=cmesh_list),
        )

    return cmesh_list, kubeconfig_global

def get_config_value(key, default=None, value_type=str):
    try:
        value = config.require(key)
        return value_type(value)
    except pulumi.ConfigMissingError:
        return default
    except ValueError:
        print(f"Warning: Could not convert config '{key}' to {value_type.__name__}, using default.")
        return default

#Main
config = pulumi.Config()

cluster_number = get_config_value("clusterNumber", 2, int)
parallel = get_config_value("parallel", 3, int)
instance_type = get_config_value("instanceType", "t4g.medium")
pool_id = get_config_value("poolId", 0, int)
region = aws_tf.config.region
cluster_id_first = get_config_value("clusterIdFirstElement", pool_id*cluster_number, int) #To Manage pools of with different number of clusters

cluster_ids = list(range(cluster_id_first, cluster_number + cluster_id_first))
vpc_cidr = f"172.31.{pool_id*16}.0/20"

azs_info = aws_tf.get_availability_zones(state="available", filters=[{
    "name": "opt-in-status",
    "values": ["opt-in-not-required"],
}])
azs = azs_info.names[:2]

kubernetes_version = "1.31"
arch = "arm"

if arch == "arm":
    ami_name_regex = f"^amazon-eks-node-al2023-arm64-standard-{kubernetes_version}-v20.*"
    interfaces = "ens+"
else:
    ami_name_regex = f"^amazon-eks-node-{kubernetes_version}-v202.*"
    interfaces = "eth0"

ami = aws_tf.ec2.get_ami(
    most_recent=True,
    name_regex=ami_name_regex
    )

stack = "organization/eks-cilium-cmesh-init/generate-ca"
ref = pulumi.StackReference(stack)
ca_crt = ref.get_output("ca_crt")
ca_key = ref.get_output("ca_key")

null_sec = local.Command(f"cmd-null-security")
null_vpc = local.Command(f"cmd-null-vpc")
null_eks = local.Command(f"cmd-null-eks")

vpc = create_vpc(null_vpc, cidr=vpc_cidr)
eks_role, ec2_role = create_roles(null_sec)
eks_sg, ec2_sg = create_sg(null_sec)
cmesh_list, kubeconfig_global = create_eks(null_eks,
                                           eks_role.get_arn(),
                                           vpc.get_subnet_ids(),
                                           [eks_sg.get_id()],
                                           ec2_role.get_arn(),
                                           [ec2_sg.get_id()],
                                           ec2_role.get_profile_name(),
                                           pool_id,
                                          )

pulumi.export("kubeconfig", kubeconfig_global.stdout)
