AWS_REGIONS="eu-west-3,eu-north-1,ca-central-1,sa-east-1,ap-northeast-1,ap-southeast-2,af-south-1"
VIDEO_FILE=tgw-connect.cast

tgw-connect:
	pulumi login $(BUCKET_S3)
	pulumi stack init tgw-connect || true
	pulumi config set --stack tgw-connect awsRegions $(AWS_REGIONS)
	pulumi up --stack tgw-connect

destroy:
	pulumi login $(BUCKET_S3)
	pulumi down --stack tgw-connect

rec:
	asciinema rec $(VIDEO_FILE)

gzip:
	gzip $(VIDEO_FILE)
