CLUSTER_NUMBER=14
VPC_NUMBER=7
PARALLEL=2

cilium-connect:
	pulumi login $(BUCKET_S3)
	pulumi stack init cilium-connect || true
	pulumi config set --stack cilium-connect clusterNumber $(CLUSTER_NUMBER)
	pulumi config set --stack cilium-connect parallel $(PARALLEL)
	pulumi config set --stack cilium-connect vpcNumber $(VPC_NUMBER)
	pulumi up --stack cilium-connect

rec:
	asciinema rec cilium-connect.cast
