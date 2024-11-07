PULUMI_PARALLEL=12
CLUSTERMESH_NUMBER=2
INSTANCE_TYPE="t4g.medium"

dev:
	pulumi login $(BUCKET_S3)
	pulumi stack init dev || true
	pulumi config set --stack dev clusterNumber $(CLUSTERMESH_NUMBER)
	pulumi config set --stack dev instanceType $(INSTANCE_TYPE)
	pulumi config set --stack dev poolId 0
	pulumi up --stack dev -p $(PULUMI_PARALLEL)

dev2:
	pulumi login $(BUCKET_S3)
	pulumi stack init dev2 || true
	pulumi config set --stack dev2 clusterNumber $(CLUSTERMESH_NUMBER)
	pulumi config set --stack dev2 instanceType $(INSTANCE_TYPE)
	pulumi config set --stack dev2 poolId 1
	pulumi up --stack dev2 -p $(PULUMI_PARALLEL)
