AWS_REGIONS="eu-west-3,sa-east-1"
TGW_REGION="eu-west-3"

tgw-connect:
	pulumi login $(BUCKET_S3)
	pulumi stack init tgw-connect || true
	pulumi config set --stack tgw-connect awsRegions $(AWS_REGIONS)
	pulumi config set --stack tgw-connect aws:region $(TGW_REGION)
	pulumi up --stack tgw-connect

destroy:
	pulumi login $(BUCKET_S3)
	pulumi down --stack tgw-connect
