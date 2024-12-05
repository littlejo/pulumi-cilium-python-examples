VIDEO_FILE="generate-ca.cast"

generate-ca:
	pulumi login $(BUCKET_S3)
	pulumi stack init generate-ca || true
	pulumi up --stack generate-ca

rec:
	asciinema rec $(VIDEO_FILE)

gzip:
	gzip $(VIDEO_FILE)
