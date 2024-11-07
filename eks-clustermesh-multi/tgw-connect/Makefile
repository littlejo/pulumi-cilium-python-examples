AWS_REGIONS="us-east-1,us-east-1,us-east-1"

cilium-connect:
	pulumi login $(BUCKET_S3)
	pulumi stack init tgw-connect || true
	pulumi config set --stack tgw-connect awsRegions $(AWS_REGIONS)
	pulumi up --stack tgw-connect
