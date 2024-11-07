CLUSTER_NUMBER=6
VPC_NUMBER=3
PARALLEL=3
INSTANCE_TYPE="t4g.medium"

cilium-connect:
	pulumi login $(BUCKET_S3)
	pulumi stack init cilium-connect || true
	pulumi config set --stack cilium-connect clusterNumber $(CLUSTER_NUMBER)
	pulumi config set --stack cilium-connect parallel $(PARALLEL)
	pulumi config set --stack cilium-connect vpcNumber $(VPC_NUMBER)
	pulumi up --stack cilium-connect
