CLUSTERMESH_NUMBER=4
POOL_NUMBER=3
INSTANCE_TYPE="t4g.medium"

cilium-connect:
	pulumi login $(BUCKET_S3)
	pulumi stack init tgw-connect || true
	pulumi config set --stack tgw-connect poolNumber $(POOL_NUMBER)
	pulumi up --stack tgw-connect
