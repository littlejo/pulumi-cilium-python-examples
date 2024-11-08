AWS_REGIONS="us-east-1,us-east-1,us-east-1"
TGW_REGION="us-east-1"

cilium-connect:
	pulumi login $(BUCKET_S3)
	pulumi stack init tgw-connect || true
	pulumi config set --stack tgw-connect awsRegions $(AWS_REGIONS)
	pulumi config set --stack tgw-connect aws:region $(TGW_REGION)
	pulumi up --stack tgw-connect

down:
	pulumi login $(BUCKET_S3)
	pulumi down --stack tgw-connect
