import pulumi
import pulumi_aws as aws_tf

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
]
cidr_blocks = cidr_blocks[:len(aws_regions)]

def create_aws_connection(i, region="us-east-1"):
    aws = aws_tf.Provider(f"aws-{region}-{i}", region=region, opts=pulumi.ResourceOptions(parent=transit_gateway))

    ## Datasources:
    vpc = aws_tf.ec2.get_vpc(tags={"Name": f"private-{region}-{i}"}, opts=pulumi.InvokeOptions(provider=aws))
    subnets = aws_tf.ec2.get_subnets(tags={"Name": f"subnet-private-*-private-{region}-{i}"}, opts=pulumi.InvokeOptions(provider=aws))
    route_table = aws_tf.ec2.get_route_table(tags={"Name": f"vpc-rt-private-private-{region}-{i}"}, opts=pulumi.InvokeOptions(provider=aws))

    tgw_attachment = aws_tf.ec2transitgateway.VpcAttachment(f"tgw-attachment-vpc-{region}-{i}",
        transit_gateway_id=transit_gateway.id,
        vpc_id=vpc.id,
        subnet_ids=subnets.ids,
        opts=pulumi.ResourceOptions(parent=aws, provider=aws))
    for cidr_block in cidr_blocks:
        if cidr_block != vpc.cidr_block:
            aws_tf.ec2.Route(f"route-vpc-{region}-{i}-{cidr_block}",
                route_table_id=route_table.id,
                destination_cidr_block=cidr_block,
                transit_gateway_id=transit_gateway.id,
                opts=pulumi.ResourceOptions(parent=tgw_attachment, provider=aws))

# Main
transit_gateway = aws_tf.ec2transitgateway.TransitGateway("tgw")
# RAM
#resource_share = aws_tf.ram.ResourceShare("example-resource-share",
#    allow_external_principals=True)
#
#resource_association = aws_tf.ram.PrincipalAssociation("example-principal-association",
#    resource_share_arn=resource_share.arn,
#    principal=peer_account_id)

# Ajouter la Transit Gateway au partage de ressources
#tgw_association = aws_tf.ram.ResourceAssociation("example-tgw-association",
#    resource_share_arn=resource_share.arn,
#    resource_arn=transit_gateway.arn)


for i, region in enumerate(aws_regions):
    create_aws_connection(i, region=region)
