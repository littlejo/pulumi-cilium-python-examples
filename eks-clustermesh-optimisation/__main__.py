#TODO
import pulumi
import pulumi_aws_native as aws_native
import pulumi_aws as aws_tf
from pulumi_command import local
import littlejo_cilium as cilium
import itertools
import ipaddress
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
    connections_list_cst = connections_list[:]

    for conn in connections_list_cst:
        if conn in connections_list:
           intersect = intersection(connections_list, conn)
           for i in intersect:
               connections_list.remove(i)
           res += [intersect]
           flat_res += intersect
    return (flat_res, res)

def tags_format(tags_dict):
    return [ {'key': k, 'value': v} for k, v in tags_dict.items() ]

class VPC:
   def __init__(self, name, cidr="10.0.0.0/16", azs=[], parent=None):
       self.name = name
       self.cidr = cidr
       self.parent = parent
       self.create_vpc()
       new_prefix = int(cidr.split("/")[1])+1
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
           opts=pulumi.ResourceOptions(parent=self.parent),
           tags=tags_format(tags)
       )

   def get_vpc_id(self):
       return self.vpc.vpc_id

   def get_subnet_ids(self):
       return [self.subnet1.subnet_id, self.subnet2.subnet_id]

   def create_subnets(self):
       tags = {
         "Name": f"subnet-{self.name}-1"
       }
       self.subnet1 = aws_native.ec2.Subnet(
           f"vpc-subnet-{self.name}-1",
           vpc_id=self.vpc.id,
           cidr_block=self.subnet_cidr[0].with_prefixlen,
           availability_zone=self.azs[0],
           opts=pulumi.ResourceOptions(parent=self.vpc),
           map_public_ip_on_launch=True,
           tags=tags_format(tags),
       )
       tags = {
         "Name": f"subnet-{self.name}-2"
       }
       self.subnet2 = aws_native.ec2.Subnet(
           f"vpc-subnet-{self.name}-2",
           vpc_id=self.vpc.id,
           cidr_block=self.subnet_cidr[1].with_prefixlen,
           availability_zone=self.azs[1],
           opts=pulumi.ResourceOptions(parent=self.vpc),
           map_public_ip_on_launch=True,
           tags=tags_format(tags),
       )
   def create_internet_gateway(self):
       self.igw = aws_native.ec2.InternetGateway(f"vpc-igw-{self.name}",
                                                opts=pulumi.ResourceOptions(parent=self.parent))
       aws_native.ec2.VpcGatewayAttachment(f"vpc-igw-attachment-{self.name}",
                                 vpc_id=self.vpc.id,
                                 internet_gateway_id=self.igw.id,
                                 opts=pulumi.ResourceOptions(parent=self.igw),
                         )

   def create_route_table(self):
       self.rt = aws_native.ec2.RouteTable(f"vpc-rt-{self.name}",
                                           vpc_id=self.vpc.id,
                                           opts=pulumi.ResourceOptions(parent=self.vpc),
                                          )

       self.r = aws_native.ec2.Route(f"vpc-rt-r-{self.name}",
                                           route_table_id=self.rt.id,
                                           destination_cidr_block="0.0.0.0/0",
                                           gateway_id=self.igw.id,
                                           opts=pulumi.ResourceOptions(parent=self.rt),
                                          )
       aws_native.ec2.SubnetRouteTableAssociation(f"vpc-rt-assoc-{self.name}-1",
                                                  route_table_id=self.rt.id,
                                                  subnet_id=self.subnet1,
                                                  opts=pulumi.ResourceOptions(parent=self.rt))

       aws_native.ec2.SubnetRouteTableAssociation(f"vpc-rt-assoc-{self.name}-2",
                                                  route_table_id=self.rt.id,
                                                  subnet_id=self.subnet2,
                                                  opts=pulumi.ResourceOptions(parent=self.rt))

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
       self.sg = aws_native.ec2.SecurityGroup(
           f"sg-{self.name}",
           vpc_id=self.vpc_id,
           group_name=self.name,
           group_description=self.description,
           opts=pulumi.ResourceOptions(parent=self.parent),
       )
       self.create_egresses()
       self.create_ingresses()

   def create_egresses(self):
       if len(self.egresses) == 0:
           egress = aws_native.ec2.SecurityGroupEgress(
               f"sg-egress-{self.name}", group_id=self.sg.group_id, ip_protocol="-1", cidr_ip="0.0.0.0/0", opts=pulumi.ResourceOptions(parent=self.sg)
           )
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
               opts=pulumi.ResourceOptions(parent=self.sg),
           )

   def get_id(self):
       return self.sg.group_id

class IAMRole:
   def __init__(self, name, trust_identity="", managed_policies=[], parent=None):
      self.managed_policy_arns = [f"arn:aws:iam::aws:policy/{p}" for p in managed_policies]
      self.service = trust_identity
      self.parent = parent
      self.name = name
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

   def cmesh_connection(self, name, destination_context=None, depends_on=[]):
       self.cmesh_connect = cilium.ClustermeshConnection(f"cilium-cmesh-connect-{name}",
                                                         destination_context=destination_context,
                                                         opts=pulumi.ResourceOptions(parent=self.provider,
                                                                                     depends_on=depends_on,
                                                                                     providers=[self.provider])
                                                        )
   def get_cmesh_enable(self):
       return self.cmesh

class EKS:
   def __init__(self, name, id="", role_arn="", subnet_ids=[], sg_ids=[], version="1.30", ec2_role_arn="", parent=None):
       self.name = name
       self.id = id
       self.role_arn = role_arn
       self.subnet_ids = subnet_ids
       self.sg_ids = sg_ids
       self.version = version
       self.ec2_role_arn = ec2_role_arn
       self.parent = parent
       self.create_eks()

   def create_eks(self):
       self.cluster = aws_native.eks.Cluster(
           f"eks-cp-{self.name}",
           name=self.name,
           role_arn=self.role_arn,
           resources_vpc_config=aws_tf.eks.ClusterVpcConfigArgs(
               subnet_ids=self.subnet_ids,
               security_group_ids=self.sg_ids,
               endpoint_public_access=True,
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
       substitute = {
                     'EKS_NAME': self.cluster.name,
                     'B64_CLUSTER_CA': self.cluster.certificate_authority_data,
                     'API_SERVER_URL': self.cluster.endpoint,
                     'K8S_CLUSTER_DNS_IP': "10.100.0.10"
                    }
       tags_dict = {
                     'Name': f"ec2-{self.name}",
                     f'kubernetes.io/cluster/{self.name}': "owned",
                     f'k8s.io/cluster/{self.name}': "owned",
                   }

       tags = [ {'key': k, 'value': v} for k, v in tags_dict.items() ]

       userdata = local.Command(f"cmd-userdata-ec2-{self.name}",
               create=f"envsubst < {template_name} | base64", #TOFIX
               environment=substitute,
               opts=pulumi.ResourceOptions(parent=self.cluster),
           )
       self.ec2 = aws_native.ec2.Instance(f"ec2-{self.name}",
                                     instance_type=instance_type,
                                     subnet_id=self.subnet_ids[self.id % 2],
                                     image_id=ami.image_id,
                                     iam_instance_profile=ec2_role.get_profile_name(),
                                     security_group_ids=[ec2_sg.get_id()],
                                     user_data=userdata.stdout,
                                     tags=tags,
                                     opts=pulumi.ResourceOptions(parent=userdata),
                                    )

   def create_kubeconfig_eks(self):
       self.kubeconfig_eks = local.Command(f"cmd-kubeconfig-{self.name}",
               create=f"aws eks update-kubeconfig --name {self.name} --kubeconfig kubeconfig-{self.name}.yaml",
               delete=f"rm -f kubeconfig-{self.name}.yaml",
               opts=pulumi.ResourceOptions(parent=self.cluster)
       )

   def create_kubeconfig_sa(self):
       self.kubeconfig = f"kubeconfig-sa-{self.id}"
       self.kubeconfig_sa = local.Command(f"cmd-kubeconfig-sa-{self.name}",
               create=f"bash helper/creation-kubeconfig.sh {self.id} {self.kubeconfig}",
               delete=f"rm -f {self.kubeconfig}",
               environment={"KUBECONFIG": f"kubeconfig-{self.name}.yaml"},
               opts=pulumi.ResourceOptions(parent=self.kubeconfig_eks)
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
       aws_native.eks.AccessEntry(f"eks-access-entry-ec2-{self.name}",
           cluster_name=self.name,
           principal_arn=self.ec2_role_arn,
           type="EC2_LINUX",
           opts=pulumi.ResourceOptions(parent=self.cluster),
       )

   def add_dns_addon(self):
       aws_native.eks.Addon(f"eks-addon-dns-{self.name}",
           addon_name="coredns",
           cluster_name=self.name,
           opts=pulumi.ResourceOptions(parent=self.cluster),
       )

   def add_kubeproxy_addon(self):
       aws_native.eks.Addon(f"eks-addon-kubeproxy-{self.name}",
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
    vpc = VPC("public", azs=azs, parent=null_vpc, cidr=cidr)
    vpc.create_subnets()
    vpc.create_internet_gateway()
    vpc.create_route_table()
    return vpc

def create_roles(null_sec):
    eks_role = IAMRole("eks-cp", trust_identity="eks.amazonaws.com", managed_policies=["AmazonEKSClusterPolicy"], parent=null_sec)
    ec2_role = IAMRole("eks-ec2", trust_identity="ec2.amazonaws.com", managed_policies=["AmazonEC2ContainerRegistryReadOnly", "AmazonEKS_CNI_Policy", "AmazonEKSWorkerNodePolicy"], parent=null_sec)
    ec2_role.create_profile()
    return eks_role, ec2_role

def create_sg(null_sec):
    eks_sg = SecurityGroup("eks-cp", vpc_id=vpc.get_vpc_id(), description="EKS control plane security group", ingresses=[{"ip_protocol": "tcp", "cidr_ip": "0.0.0.0/0", "from_port": 443, "to_port": 443}], parent=null_sec)
    ec2_sg = SecurityGroup("eks-worker", vpc_id=vpc.get_vpc_id(), description="EKS nodes security group", parent=null_sec, ingresses= [
                                                              {"ip_protocol": "-1", "source_security_group_id": "self", "from_port": -1, "to_port": -1},
                                                              {"ip_protocol": "-1", "source_security_group_id": eks_sg.get_id(), "from_port": -1, "to_port": -1},
                                                              {"ip_protocol": "tcp", "cidr_ip": "0.0.0.0/0", "from_port": 30000, "to_port": 32767},
                                                              {"ip_protocol": "icmp", "cidr_ip": "0.0.0.0/0", "from_port": -1, "to_port": -1},
                                                             ])
    return eks_sg, ec2_sg

def create_eks(null_eks):
    cmesh_list = []
    kubeconfigs = []
    for i in cluster_ids:
        cilium_sets = [
                             f"cluster.name=cmesh{i}",
                             f"cluster.id={i}",
                             f"egressMasqueradeInterfaces={interfaces}",
                             f"operator.replicas=1",
                             f'ipam.mode=cluster-pool',
                             f'routingMode=tunnel',
                             'ipam.operator.clusterPoolIPv4PodCIDRList={10.%s.0.0/16}' % i,
        ]
        eks_cluster = EKS(f"eksCluster-{i}",
                          id=i,
                          role_arn=eks_role.get_arn(),
                          subnet_ids=vpc.get_subnet_ids(),
                          sg_ids=[eks_sg.get_id()],
                          version=kubernetes_version,
                          ec2_role_arn=ec2_role.get_arn(),
                          parent=null_eks)
        eks_cluster.add_node_access()
        eks_cluster.add_dns_addon()
        eks_cluster.add_kubeproxy_addon()
        eks_cluster.create_kubeconfig_eks()
        eks_cluster.create_kubeconfig_sa()
        eks_cluster.create_ec2()
        eks_cluster.add_cilium(config_path=eks_cluster.get_kubeconfig(), parent=eks_cluster.get_kubeconfig_sa(), sets=cilium_sets, cmesh_service="NodePort", depends_on=[eks_cluster.get_ec2()])
        cmesh_list += eks_cluster.get_cilium_cmesh()
        kubeconfigs += [ eks_cluster.get_kubeconfig() ]

    kubeconfig_global = local.Command("cmd-kubeconfig-connect",
            create="kubectl config view --raw > ./kubeconfig.yaml",
            delete=f"rm -f kubeconfig.yaml",
            environment={"KUBECONFIG": ":".join(kubeconfigs)},
            opts=pulumi.ResourceOptions(depends_on=cmesh_list),
        )

    return cmesh_list, kubeconfig_global

def create_connections():
    null = []
    cmesh_connect = []
    depends_on = []
    l = 0
    k = 0
    connections_list = combinlist(cluster_ids)
    flat_connections_list, connect_list = combi_optimization(connections_list)
    for connections in connect_list:
        null += [local.Command(f"cmd-null-connect-{l}", opts=pulumi.ResourceOptions(depends_on=cmesh_list, parent=kubeconfig_global))]
        for conn in connections:
            i = conn[0]
            j = conn[1]
            cilium_connect = Cilium(f"cmesh-{k}", config_path=f"./kubeconfig.yaml", parent=null[l], context=f"eksCluster-{j}", depends_on=kubeconfig_global)
            cilium_connect.cmesh_connection(f"{i}-{j}", destination_context=f"eksCluster-{i}", depends_on=depends_on)
            cmesh_connect += [cilium_connect.cmesh_connect]
            k += 1
        depends_on += cmesh_connect + null
        l += 1

#Main
config = pulumi.Config()
try:
    cluster_number = int(config.require("clusterNumber"))
except:
    cluster_number = 4
cluster_ids = list(range(1, cluster_number+1))

region = aws_tf.config.region
azs = [f"{region}a", f"{region}b"]

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

null_sec = local.Command(f"cmd-null-security")
null_vpc = local.Command(f"cmd-null-vpc")
null_eks = local.Command(f"cmd-null-eks")

vpc = create_vpc(null_vpc, cidr="172.31.0.0/16")
eks_role, ec2_role = create_roles(null_sec)
eks_sg, ec2_sg = create_sg(null_sec)
cmesh_list, kubeconfig_global = create_eks(null_eks)

create_connections()
