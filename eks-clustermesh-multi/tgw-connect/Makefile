AWS_REGIONS="us-east-1,us-west-2"

tgw-connect:
	pulumi login $(BUCKET_S3)
	pulumi stack init tgw-connect || true
	pulumi config set --stack tgw-connect awsRegions $(AWS_REGIONS)
	pulumi up --stack tgw-connect

destroy:
	pulumi login $(BUCKET_S3)
	pulumi down --stack tgw-connect

rec:
	asciinema rec tgw.cast
