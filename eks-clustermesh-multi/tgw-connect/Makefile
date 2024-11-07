CLUSTERMESH_NUMBER=4
INSTANCE_TYPE="t4g.medium"

cilium-connect:
	pulumi login $(BUCKET_S3)
	pulumi stack init tgw-connect
	pulumi up --stack tgw-connect
