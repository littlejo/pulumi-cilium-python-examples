"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws
import pulumi_aws_native as aws_native
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
   def __init__(self, name, aws, aws_tf, cidr="10.0.0.0/16", azs=[], parent=None):
       self.name = name
       self.cidr = cidr
       self.parent = parent
       self.aws = aws
       self.aws_tf = aws_tf
       self.create_vpc()
       new_prefix = int(cidr.split("/")[1])+2
       self.azs = azs
       self.subnet_cidr = list(ipaddress.ip_network(cidr).subnets(new_prefix=new_prefix))

   def create_vpc(self):
       tags = {
         "Name": self.name
       }
       self.vpc = aws_native.ec2.Vpc(
           f"vpc-{self.name}",
           cidr_block=self.cidr,
           enable_dns_hostnames=True,
           enable_dns_support=True,
           opts=pulumi.ResourceOptions(parent=self.parent, providers=[self.aws]),
           tags=tags_format(tags)
       )

   def get_vpc_id(self):
       return self.vpc.vpc_id

   def get_subnet_ids(self):
       return [self.private_subnet1.subnet_id, self.private_subnet2.subnet_id]

   def create_subnets(self):
       tags = {
         "Name": f"subnet-public-{self.name}-1"
       }
       self.subnet1 = aws_native.ec2.Subnet(
           f"vpc-subnet-public-{self.name}-1",
           vpc_id=self.vpc.id,
           cidr_block=self.subnet_cidr[0].with_prefixlen,
           availability_zone=self.azs[0],
           opts=pulumi.ResourceOptions(parent=self.vpc, providers=[self.aws]),
           map_public_ip_on_launch=True,
           tags=tags_format(tags),
       )
       tags = {
         "Name": f"subnet-public-{self.name}-2"
       }
       self.subnet2 = aws_native.ec2.Subnet(
           f"vpc-subnet-public-{self.name}-2",
           vpc_id=self.vpc.id,
           cidr_block=self.subnet_cidr[1].with_prefixlen,
           availability_zone=self.azs[1],
           opts=pulumi.ResourceOptions(parent=self.vpc, providers=[self.aws]),
           map_public_ip_on_launch=True,
           tags=tags_format(tags),
       )
       tags = {
         "Name": f"subnet-private-{self.name}-1"
       }
       self.private_subnet1 = aws_native.ec2.Subnet(
           f"vpc-private-subnet-{self.name}-1",
           vpc_id=self.vpc.id,
           cidr_block=self.subnet_cidr[2].with_prefixlen,
           availability_zone=self.azs[0],
           opts=pulumi.ResourceOptions(parent=self.vpc, providers=[self.aws]),
           tags=tags_format(tags),
       )
       tags = {
         "Name": f"subnet-private-{self.name}-2"
       }
       self.private_subnet2 = aws_native.ec2.Subnet(
           f"vpc-private-subnet-{self.name}-2",
           vpc_id=self.vpc.id,
           cidr_block=self.subnet_cidr[3].with_prefixlen,
           availability_zone=self.azs[1],
           opts=pulumi.ResourceOptions(parent=self.vpc, providers=[self.aws]),
           tags=tags_format(tags),
       )
   def create_nat_gateway(self):
       tags = {
         "Name": self.name
       }
       nat_eip = aws.ec2.Eip(f"vpc-eip-{self.name}",
           opts = pulumi.ResourceOptions(parent=self.igw, providers=[self.aws_tf]),
	   tags = tags,
       )
       self.nat_gw = aws.ec2.NatGateway(f"vpc-nat-gw-{self.name}",
           allocation_id=nat_eip.id,
           subnet_id=self.subnet1,
	   tags = tags,
           opts = pulumi.ResourceOptions(parent=nat_eip, providers=[self.aws_tf])
       )

   def create_internet_gateway(self):
       self.igw = aws_native.ec2.InternetGateway(f"vpc-igw-{self.name}",
                                                opts=pulumi.ResourceOptions(parent=self.parent, providers=[self.aws]))
       aws_native.ec2.VpcGatewayAttachment(f"vpc-igw-attachment-{self.name}",
                                 vpc_id=self.vpc.id,
                                 internet_gateway_id=self.igw.id,
                                 opts=pulumi.ResourceOptions(parent=self.igw, providers=[self.aws]),
                         )

   def create_route_table(self):
       tags = {
         "Name": f"vpc-rt-public-{self.name}",
       }
       self.rt = aws_native.ec2.RouteTable(f"vpc-rt-public-{self.name}",
                                           vpc_id=self.vpc.id,
                                           opts=pulumi.ResourceOptions(parent=self.vpc, providers=[self.aws]),
                                           tags=tags_format(tags),
                                          )

       self.r = aws_native.ec2.Route(f"vpc-rt-r-public-{self.name}",
                                           route_table_id=self.rt.id,
                                           destination_cidr_block="0.0.0.0/0",
                                           gateway_id=self.igw.id,
                                           opts=pulumi.ResourceOptions(parent=self.rt, providers=[self.aws]),
                                          )
       aws_native.ec2.SubnetRouteTableAssociation(f"vpc-rt-assoc-public-{self.name}-1",
                                                  route_table_id=self.rt.id,
                                                  subnet_id=self.subnet1,
                                                  opts=pulumi.ResourceOptions(parent=self.rt, providers=[self.aws]))

       aws_native.ec2.SubnetRouteTableAssociation(f"vpc-rt-assoc-public-{self.name}-2",
                                                  route_table_id=self.rt.id,
                                                  subnet_id=self.subnet2,
                                                  opts=pulumi.ResourceOptions(parent=self.rt, providers=[self.aws]))

       tags = {
         "Name": f"vpc-rt-private-{self.name}",
       }
       self.rt_pv = aws_native.ec2.RouteTable(f"vpc-rt-private-{self.name}",
                                           vpc_id=self.vpc.id,
                                           tags=tags_format(tags),
                                           opts=pulumi.ResourceOptions(parent=self.vpc, providers=[self.aws]),
                                          )

       self.r_pv = aws_native.ec2.Route(f"vpc-rt-r-private-{self.name}",
                                           route_table_id=self.rt_pv.id,
                                           destination_cidr_block="0.0.0.0/0",
                                           nat_gateway_id=self.nat_gw.id,
                                           opts=pulumi.ResourceOptions(parent=self.rt_pv, providers=[self.aws]),
                                          )

       aws_native.ec2.SubnetRouteTableAssociation(f"vpc-rt-assoc-private-{self.name}-1",
                                                  route_table_id=self.rt_pv.id,
                                                  subnet_id=self.private_subnet1,
                                                  opts=pulumi.ResourceOptions(parent=self.rt_pv, providers=[self.aws]))

       aws_native.ec2.SubnetRouteTableAssociation(f"vpc-rt-assoc-private-{self.name}-2",
                                                  route_table_id=self.rt_pv.id,
                                                  subnet_id=self.private_subnet2,
                                                  opts=pulumi.ResourceOptions(parent=self.rt_pv, providers=[self.aws]))

class IAMRole:
   def __init__(self, name, aws, aws_tf, trust_identity="", managed_policies=[], profile="", region="",parent=None):
      self.managed_policy_arns = [f"arn:aws:iam::aws:policy/{p}" for p in managed_policies]
      self.service = trust_identity
      self.parent = parent
      self.name = name
      self.aws = aws_tf
      self.create_role()

   def create_role(self):
      self.role = aws_native.iam.Role(
          f"iam-role-{self.name}",
          role_name=self.name,
          assume_role_policy_document=pulumi.Output.from_input(
              self.get_assume_role_policy_document()
          ),
          managed_policy_arns=self.managed_policy_arns,
          opts=pulumi.ResourceOptions(parent=self.parent),
      )

   def create_profile(self):
      self.profile = aws_native.iam.InstanceProfile(f"iam-profile-{self.name}",
          path="/",
          roles=[self.role.role_name],
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
       return self.profile.instance_profile_name

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

   def cmesh_connection(self, name, destination_contexts=None, connection_mode="bidirectional", depends_on=[]):
       self.cmesh_connect = cilium.ClustermeshConnection(f"cilium-cmesh-connect-{name}",
                                                         destination_contexts=destination_contexts,
                                                         connection_mode=connection_mode,
                                                         opts=pulumi.ResourceOptions(parent=self.provider,
                                                                                     depends_on=depends_on,
                                                                                     providers=[self.provider])
                                                        )
   def get_cmesh_enable(self):
       return self.cmesh

class EKS:
   def __init__(self, name, aws, aws_tf, id="", role_arn="", subnet_ids=[], sg_ids=[], version="1.30", ami="",ec2_role_arn="", ec2_sg_ids=[], ec2_profile_name="", parent=None):
       self.name = name
       self.profile = name.split('-')[1]
       self.id = id
       self.role_arn = role_arn
       self.subnet_ids = subnet_ids
       self.sg_ids = sg_ids
       self.version = version
       self.ami = ami
       self.parent = parent
       self.aws = aws
       self.aws_tf = aws_tf
       self.create_eks()
       self.ec2 = {
         "role_arn": ec2_role_arn,
         "sg_ids": ec2_sg_ids,
         "profile_name": ec2_profile_name,
       }

   def create_eks(self):
       self.cluster = aws.eks.Cluster(
           f"eks-cp-{self.name}",
           name=self.name,
           role_arn=self.role_arn,
           vpc_config=aws.eks.ClusterVpcConfigArgs(
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
           opts=pulumi.ResourceOptions(parent=self.parent, providers=[self.aws_tf]),
       )

   def create_ec2(self):
       tags_dict = {
                     'Name': f"ec2-{self.name}",
                     f'kubernetes.io/cluster/{self.name}': "owned",
                     f'k8s.io/cluster/{self.name}': "owned",
                   }

       user_data = get_userdata(self.cluster.name, self.cluster.endpoint, self.cluster.certificate_authority["data"], self.cluster.kubernetes_network_config.service_ipv4_cidr)
       self.ec2 = aws.ec2.Instance(f"ec2-{self.name}",
                                     instance_type=instance_type,
                                     subnet_id=self.subnet_ids[self.id % 2],
                                     ami=self.get_ami_id(),
                                     iam_instance_profile=self.ec2["profile_name"],
                                     vpc_security_group_ids=self.ec2["sg_ids"],
                                     user_data=user_data,
                                     tags=tags_dict,
                                     opts=pulumi.ResourceOptions(parent=self.cluster, providers=[self.aws_tf]),
                                    )

   def create_kubeconfig_eks(self):
       self.kubeconfig_eks = local.Command(f"cmd-kubeconfig-{self.name}",
               create=f"aws eks update-kubeconfig --name {self.name} --kubeconfig kubeconfig-{self.name}.yaml",
               delete=f"rm -f kubeconfig-{self.name}.yaml",
               opts=pulumi.ResourceOptions(parent=self.cluster)
       )

   def create_kubeconfig_sa(self):
       self.kubeconfig = f"kubeconfig-sa-{self.profile}-{self.id}"
       #auth = aws_tf.eks.get_cluster_auth(name=self.cluster.cluster_id)
       self.kubeconfig_sa = local.Command(f"cmd-kubeconfig-sa-{self.name}",
               create=f"bash helper/creation-kubeconfig.sh {self.kubeconfig}",
               delete=f"rm -f {self.kubeconfig}",
               environment={
                             "KUBECONFIG": f"kubeconfig-{self.name}.yaml",
                             "serviceaccount": f"admin-{self.profile}-{self.id}",
                             "cluster": self.name,
                             "ca": self.cluster.certificate_authority["data"],
                             "server": self.cluster.endpoint,
                             "account": self.cluster.arn,
       #                      "token": auth.token,
                           },
               opts=pulumi.ResourceOptions(parent=self.cluster)
       )

   def get_ami_id(self):
       return aws.ec2.get_ami(
                              most_recent=True,
                              name_regex=ami_name_regex,
                              opts=pulumi.InvokeOptions(provider=self.aws_tf),
                              ).id

   def get_ec2(self):
       return self.ec2

   def get_kubeconfig(self):
       return self.kubeconfig

   def get_kubeconfig_sa(self):
       return self.kubeconfig_sa

   def get_name(self):
       return self.cluster.name

   def add_node_access(self):
       aws_native.eks.AccessEntry(f"eks-access-entry-ec2-{self.name}",
           cluster_name=self.name,
           principal_arn=self.ec2["role_arn"],
           type="EC2_LINUX",
           opts=pulumi.ResourceOptions(parent=self.cluster, providers=[self.aws]),
       )

   def add_dns_addon(self):
       aws_native.eks.Addon(f"eks-addon-dns-{self.name}",
           addon_name="coredns",
           cluster_name=self.name,
           opts=pulumi.ResourceOptions(parent=self.cluster, providers=[self.aws]),
       )

   def add_kubeproxy_addon(self):
       aws_native.eks.Addon(f"eks-addon-kubeproxy-{self.name}",
           addon_name="kube-proxy",
           cluster_name=self.name,
           opts=pulumi.ResourceOptions(parent=self.cluster, providers=[self.aws]),
       )

   def add_cilium(self, config_path="", parent=None, depends_on=[], version="1.16.0", sets=[], cmesh_service=""):
       self.cilium = Cilium(self.name, config_path=self.kubeconfig, parent=self.kubeconfig_sa, depends_on=depends_on)
       self.cilium.deploy(version, sets=sets)
       if cmesh_service != "":
           self.cilium.cmesh_enable(service_type=cmesh_service)

   def get_cilium_cmesh(self):
       return self.cilium.get_cmesh_enable()

class SecurityGroup:
   def __init__(self, name, aws, vpc_id="", description="", ingresses=[], egresses=[], parent=None):
       self.name = name
       self.aws = aws
       self.vpc_id = vpc_id
       self.description = description
       self.ingresses = ingresses
       self.egresses = egresses
       self.parent = parent
       self.create_sg()

   def create_sg(self):
       self.sg = aws_native.ec2.SecurityGroup(
           f"sg-{self.name}",
           vpc_id=self.vpc_id,
           group_name=self.name,
           group_description=self.description,
           opts=pulumi.ResourceOptions(parent=self.parent, providers=[self.aws]),
       )
       self.create_egresses()
       self.create_ingresses()

   def create_egresses(self):
       if len(self.egresses) == 0:
           egress = aws_native.ec2.SecurityGroupEgress(
               f"sg-egress-{self.name}", group_id=self.sg.group_id, ip_protocol="-1", cidr_ip="0.0.0.0/0", opts=pulumi.ResourceOptions(parent=self.sg, providers=[self.aws]))
       else:
           pass #TODO

   def create_ingresses(self):
       for i, ing in enumerate(self.ingresses):
           source_sg_id = ing.get("source_security_group_id")
           if source_sg_id == "self":
               source_sg_id = self.sg.group_id
           ingress = aws_native.ec2.SecurityGroupIngress(
               f"sg-ingress-{self.name}-{i}",
               group_id=self.sg.group_id,
               ip_protocol=ing["ip_protocol"],
               cidr_ip=ing.get("cidr_ip"),
               from_port=ing["from_port"],
               to_port=ing["to_port"],
               source_security_group_id=source_sg_id,
               opts=pulumi.ResourceOptions(parent=self.sg, providers=[self.aws]),
           )

   def get_id(self):
       return self.sg.group_id

def create_vpc(null_vpc, aws, aws_tf, cidr="", profile="", region=""):
    azs = [f"{region}a", f"{region}b"]
    vpc = VPC(f"private-{profile}", aws, aws_tf, azs=azs, parent=null_vpc, cidr=cidr)
    vpc.create_subnets()
    vpc.create_internet_gateway()
    vpc.create_nat_gateway()
    vpc.create_route_table()
    return vpc

def create_roles(null_sec, aws, aws_tf, profile="", region=""):
    eks_role = IAMRole(f"eks-cp-{profile}", aws, aws_tf, trust_identity="eks.amazonaws.com", managed_policies=["AmazonEKSClusterPolicy"], profile=profile, region=region, parent=null_sec)
    ec2_role = IAMRole(f"eks-ec2-{profile}", aws, aws_tf, trust_identity="ec2.amazonaws.com", managed_policies=["AmazonEC2ContainerRegistryReadOnly", "AmazonEKS_CNI_Policy", "AmazonEKSWorkerNodePolicy"], profile=profile, region=region, parent=null_sec)
    ec2_role.create_profile()
    return eks_role, ec2_role

def create_eks(null_eks, aws, aws_tf, role_arn, subnet_ids, sg_ids, ec2_role_arn, ec2_sg_ids, ec2_profile_name, index, cluster_number,profile="", region=""):
    cmesh_list = []
    kubeconfigs = []
    contexts = []
    cluster_ids = list(range(cluster_number))
    for i in cluster_ids:
        context = f"eksCluster-{profile}-{i}"
        contexts += [context]
        cilium_sets = [
                             f"cluster.name=cmesh-{profile}-{index+i+1}",
                             f"cluster.id={index+i+1}",
                             f"egressMasqueradeInterfaces={interfaces}",
                             f"operator.replicas=1",
                             f'ipam.mode=cluster-pool',
                             f'routingMode=tunnel',
                             'ipam.operator.clusterPoolIPv4PodCIDRList={10.%s.%s.0/24}' % (index + i // 256, i % 256),
        ]
        eks_cluster = EKS(context,
                          aws,
                          aws_tf,
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
        eks_cluster.add_dns_addon()
        eks_cluster.add_kubeproxy_addon()
        eks_cluster.create_kubeconfig_sa()
        eks_cluster.create_ec2()
        eks_cluster.add_cilium(config_path=eks_cluster.get_kubeconfig(), parent=eks_cluster.get_kubeconfig_sa(), sets=cilium_sets, cmesh_service="NodePort", depends_on=[eks_cluster.get_ec2()])
        cmesh_list += eks_cluster.get_cilium_cmesh()
        kubeconfigs += [ eks_cluster.get_kubeconfig() ]

    return cmesh_list, kubeconfigs, contexts

def create_sg(null_sec, aws, vpc_id="", profile="", region=""):
    eks_sg = SecurityGroup(f"eks-cp-{profile}", aws, vpc_id=vpc_id, description="EKS control plane security group", ingresses=[{"ip_protocol": "tcp", "cidr_ip": "0.0.0.0/0", "from_port": 443, "to_port": 443}], parent=null_sec)
    ec2_sg = SecurityGroup(f"eks-worker-{profile}", aws, vpc_id=vpc_id, description="EKS nodes security group", parent=null_sec, ingresses= [
                                                              {"ip_protocol": "-1", "source_security_group_id": "self", "from_port": -1, "to_port": -1},
                                                              {"ip_protocol": "-1", "source_security_group_id": eks_sg.get_id(), "from_port": -1, "to_port": -1},
                                                              {"ip_protocol": "tcp", "cidr_ip": "0.0.0.0/0", "from_port": 30000, "to_port": 32767},
                                                              {"ip_protocol": "icmp", "cidr_ip": "0.0.0.0/0", "from_port": -1, "to_port": -1},
                                                             ])
    return eks_sg, ec2_sg

kubernetes_version = "1.30"
arch = "arm"

if arch == "arm":
    ami_name_regex = f"^amazon-eks-node-al2023-arm64-standard-{kubernetes_version}-v20.*"
    instance_type = "t4g.medium"
    interfaces = "ens+"
else:
    ami_name_regex = f"^amazon-eks-node-{kubernetes_version}-v202.*"
    instance_type = "t3.micro"
    interfaces = "eth0"

null_acc1 = local.Command(f"cmd-null-account1")
null_acc2 = local.Command(f"cmd-null-account2")

profile1 = "acg1"
profile2 = "acg2"

acg1 = {"profile": profile1, "region": "us-east-1"}
acg2 = {"profile": profile2, "region": "us-west-2"}

aws_tf1 = aws.Provider("aws-tf1", **acg1, opts=pulumi.ResourceOptions(parent=null_acc1))
aws_tf2 = aws.Provider("aws-tf2", **acg2, opts=pulumi.ResourceOptions(parent=null_acc2))

aws1 = aws_native.Provider("aws1", **acg1, opts=pulumi.ResourceOptions(parent=null_acc1))
aws2 = aws_native.Provider("aws2", **acg2, opts=pulumi.ResourceOptions(parent=null_acc2))

data = {
   "acc1": {
     "null": null_acc1,
     "pvd1": aws1,
     "pvd2": aws_tf1,
     "cidr": "172.31.0.0/16",
     "profile-region": acg1,
     "cluster_number": 2
   },
   "acc2": {
     "null": null_acc2,
     "pvd1": aws2,
     "pvd2": aws_tf2,
     "cidr": "192.168.0.0/16",
     "profile-region": acg2,
     "cluster_number": 2
   }
}

kubeconfigs_list = []
contexts_list = []
cmeshes_list = []
cluster_number_index = 0

for k, v in data.items():
    vpc = create_vpc(v["null"], v["pvd1"], v["pvd2"], cidr=v["cidr"], **v["profile-region"])
    eks_role, ec2_role = create_roles(v["null"], v["pvd1"], v["pvd2"], **v["profile-region"])
    eks_sg, ec2_sg = create_sg(v["null"], v["pvd1"], vpc.get_vpc_id(), **v["profile-region"])

    cmesh_list, kubeconfigs, contexts = create_eks(v["null"],
                                               v["pvd1"], v["pvd2"],
                                               eks_role.get_arn(),
                                               vpc.get_subnet_ids(),
                                               [eks_sg.get_id()],
                                               ec2_role.get_arn(),
                                               [ec2_sg.get_id()],
                                               ec2_role.get_profile_name(),
                                               cluster_number_index,
                                               v["cluster_number"],
                                               **v["profile-region"]
                                              )
    if cluster_number_index == 0:
        cluster_number_index += v["cluster_number"] + 1
    kubeconfigs_list += kubeconfigs
    contexts_list += contexts
    cmeshes_list += cmesh_list

#TOFIX:
#* VPC_PEER
#* ROUTE TABLE

kubeconfig_global = local.Command(f"cmd-kubeconfig-connect",
        create=f"kubectl config view --raw > ./kubeconfig.yaml",
        delete=f"rm -f kubeconfig.yaml",
        environment={"KUBECONFIG": ":".join(kubeconfigs_list)},
        opts=pulumi.ResourceOptions(depends_on=cmeshes_list),
    )

local_context = contexts_list[0]
remote_contexts = contexts_list[1:]

#pulumi.log.info(f"local_context: {local_context}, type: {type(local_context)}")
cilium_connect = Cilium(f"cmesh", config_path=f"./kubeconfig.yaml", context=local_context, depends_on=[kubeconfig_global])
cilium_connect.cmesh_connection(f"cmesh-connect", destination_contexts=remote_contexts, depends_on=[kubeconfig_global])
