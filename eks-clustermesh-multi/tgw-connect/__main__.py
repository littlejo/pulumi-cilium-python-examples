import pulumi
import pulumi_aws as aws
from pulumi_command import local

class ROUTETGW(pulumi.ComponentResource):
   def __init__(self, name, destination_cidr_block="", transit_gateway_attachment_id="", transit_gateway_route_table_id="", opts=None):
       super().__init__('custom-aws:route-tgw', name, None, opts)
       aws.ec2transitgateway.Route(
           f"static-route-{name}",
           destination_cidr_block=destination_cidr_block,
           transit_gateway_attachment_id=transit_gateway_attachment_id,
           transit_gateway_route_table_id=transit_gateway_route_table_id,
           opts=opts
       )
       aws.ec2transitgateway.RouteTableAssociation(
           f"route-table-association-{name}",
           transit_gateway_attachment_id=transit_gateway_attachment_id,
           transit_gateway_route_table_id=transit_gateway_route_table_id,
           opts=opts
       )

class TGW(pulumi.ComponentResource):
   def __init__(self, name, description='vpc', vpc_id="", subnet_ids=[], route_table_id="", cidrs=[], opts=None):
       super().__init__('custom-aws:tgw', name, None, opts)
       self.tgw = aws.ec2transitgateway.TransitGateway(name,
                                                     description=description,
                                                     auto_accept_shared_attachments="enable",
                                                     default_route_table_association="disable",
                                                     default_route_table_propagation="disable",
                                                     opts=opts)
       self.opts = opts
       self._create_vpc_attachment(vpc_id, subnet_ids)
       self._create_route_table()
       self._create_vpc_route(route_table_id, cidrs)

       self.register_outputs({
           'id': self.tgw.id,
           'rt_id': self.rt.id,
       })
       self.id = self.tgw.id
       self.rt = self.rt.id


   def _create_vpc_attachment(self, vpc_id, subnet_ids):
       attachment_opts = pulumi.ResourceOptions(parent=self.tgw)
       self.tgw_attach = aws.ec2transitgateway.VpcAttachment(
           f"{self.tgw._name}-vpc-attachment",
           subnet_ids=subnet_ids,
           transit_gateway_id=self.tgw.id,
           vpc_id=vpc_id,
           opts=pulumi.ResourceOptions.merge(self.opts, attachment_opts)
       )

   def _create_route_table(self):
       self.rt = aws.ec2transitgateway.RouteTable(
           f"{self.tgw._name}-route-table",
           transit_gateway_id=self.tgw.id,
           tags={
               "Name": f"{self.tgw._name}-route-table"
           },
           opts=self.opts
       )
       attachment_opts = pulumi.ResourceOptions(parent=self.rt)
       aws.ec2transitgateway.RouteTableAssociation(f"{self.tgw._name}-route-table",
           transit_gateway_attachment_id=self.tgw_attach.id,
           transit_gateway_route_table_id=self.rt.id,
           opts=pulumi.ResourceOptions.merge(self.opts, attachment_opts),
       )
       aws.ec2transitgateway.RouteTablePropagation(f"{self.tgw._name}-route-table",
           transit_gateway_attachment_id=self.tgw_attach.id,
           transit_gateway_route_table_id=self.rt.id,
           opts=pulumi.ResourceOptions.merge(self.opts, attachment_opts),
       )

   def _create_vpc_route(self, route_table_id, cidrs):
       attachment_opts = pulumi.ResourceOptions(parent=self.tgw)
       for cidr in cidrs:
           aws.ec2.Route(f"{self.tgw._name}-{cidr}",
              route_table_id=route_table_id,
              destination_cidr_block=cidr,
              transit_gateway_id=self.tgw.id,
              opts=pulumi.ResourceOptions.merge(self.opts, attachment_opts),
          )

class TGWATTACHMENT(pulumi.ComponentResource):
   def __init__(self, name, peer_region="", peer_transit_gateway_id="", transit_gateway_id="", route_table_id="", opts=None):
       super().__init__('custom-aws:PeeringAttachment', name, None, opts)
       self.tgw_peering = aws.ec2transitgateway.PeeringAttachment(
           name,
           peer_region=peer_region,
           peer_transit_gateway_id=peer_transit_gateway_id,
           transit_gateway_id=transit_gateway_id,
           opts=opts,
           tags={
               "Name": name,
           }
       )
       self.peer_region=peer_region
       self._create_accepter()
       self.id = self.tgw_peering.id
       self.peering_id = self.peering.ids[0]
       self._update_route_table(route_table_id)

       self.register_outputs({
           'id': self.id,
           'peering_id': self.peering_id,
       })


   def _create_accepter(self):
       self.aws_peer = aws.Provider(f"aws-{self.tgw_peering._name}", region=self.peer_region, opts=pulumi.ResourceOptions(parent=self.tgw_peering))
       self.peering = self.tgw_peering.id.apply(
           lambda _: aws.ec2transitgateway.get_peering_attachments(
               filters=[
                   {
                       "name": "transit-gateway-id",
                       "values": [self.tgw_peering.peer_transit_gateway_id],
                   },
                   {
                       "name": "state",
                       "values": ["pendingAcceptance", "available"],
                   },
               ],
               opts=pulumi.InvokeOptions(provider=self.aws_peer)
           )
       )

       self.accepter = self.peering.apply(lambda p: aws.ec2transitgateway.PeeringAttachmentAccepter(
           f"{self.tgw_peering._name}-accepter",
           transit_gateway_attachment_id=p.ids[0] if p.ids else "",
           opts=pulumi.ResourceOptions(provider=self.aws_peer, parent=self.aws_peer, ignore_changes=["transit_gateway_attachment_id"]),
       ))

   def _update_route_table(self, route_table_id):
       ROUTETGW(self.tgw_peering._name, destination_cidr_block="0.0.0.0/0",
                   transit_gateway_attachment_id=self.peering_id,
                   transit_gateway_route_table_id=route_table_id,
                   opts=pulumi.ResourceOptions(depends_on=[self.accepter], provider=self.aws_peer, parent=self.tgw_peering)
                )

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
aws_regions = get_config_value("awsRegions", "us-east-1,us-east-1").split(",")

#VPC CIDR BLOCKS ALREADY CREATED
cidr_blocks = [
    "172.31.0.0/20",
    "172.31.16.0/20",
    "172.31.32.0/20",
    "172.31.48.0/20",
    "172.31.64.0/20",
    "172.31.80.0/20",
    "172.31.96.0/20",
][:len(aws_regions)]

vpc_number = len(aws_regions)

tgw_ids = []
tgws = []
tgw_rts = []

def create_tgw(pool_id, region, cidrs):
    null_tgw = local.Command(f"tgw-{region}-{pool_id}")
    awsp = aws.Provider(f"aws-{region}-{pool_id}", region=region, opts=pulumi.ResourceOptions(parent=null_tgw))

    vpc = aws.ec2.get_vpc(tags={"Name": f"private-{region}-{pool_id}"}, opts=pulumi.InvokeOptions(provider=awsp))
    subnets = aws.ec2.get_subnets(tags={"Name": f"subnet-private-*-private-{region}-{pool_id}"}, opts=pulumi.InvokeOptions(provider=awsp))
    route_table = aws.ec2.get_route_table(tags={"Name": f"vpc-rt-private-private-{region}-{pool_id}"}, opts=pulumi.InvokeOptions(provider=awsp))

    tgw = TGW(
        f"tgw-vpc-{pool_id}",
        subnet_ids=subnets.ids,
        vpc_id=vpc.id,
        route_table_id=route_table.id,
        cidrs=cidrs,
        opts=pulumi.ResourceOptions(provider=awsp, parent=awsp)
    )
    return tgw

for pool_id, region in enumerate(aws_regions):
    cidrs = [block for i, block in enumerate(cidr_blocks) if i != pool_id]
    tgw = create_tgw(pool_id, region, cidrs)
    tgw_ids.append(tgw.id)
    tgws.append(tgw.tgw_attach)
    tgw_rts.append(tgw.rt)

tgw_peerings = []
tgw_peerings_accepter = []

for i in range(1, vpc_number):
    region = aws_regions[0]
    peer_region = aws_regions[i]
    null_tgw = local.Command(f"tgw-peering-{region}-{peer_region}-{i}")
    awsp = aws.Provider(f"aws-attachment-{region}-{i}", region=region, opts=pulumi.ResourceOptions(parent=null_tgw))
    peering = TGWATTACHMENT(
        f"tgw-peering-{i}",
        peer_region=peer_region,
        peer_transit_gateway_id=tgw_ids[i],
        transit_gateway_id=tgw_ids[0],
        route_table_id=tgw_rts[i],
        opts=pulumi.ResourceOptions(depends_on=tgws, provider=awsp, parent=awsp)
    )

    tgw_peerings.append(peering)
    tgw_peerings_accepter.append(peering.accepter)

null_route = local.Command(f"tgw-route-final", opts=pulumi.ResourceOptions(depends_on=[peering.accepter]))
for i, peering in enumerate(tgw_peerings, start=1):
    awsp = aws.Provider(f"aws-{aws_regions[0]}-route-{i}", region=aws_regions[0], opts=pulumi.ResourceOptions(parent=null_route))
    vpc_cidr = f"172.31.{i * 16}.0/20"
    ROUTETGW(f"route-tgw-{i}", destination_cidr_block=vpc_cidr,
                transit_gateway_attachment_id=peering.id,
                transit_gateway_route_table_id=tgw_rts[0],
                opts=pulumi.ResourceOptions(depends_on=[peering.accepter], provider=awsp, parent=awsp)
             )
