PULUMI_PARALLEL=146
CLUSTERMESH_NUMBER=73
INSTANCE_TYPE="t4g.medium"

.PHONY: dev0 dev1 dev2 dev3 dev4 dev5 dev6

deploy_stack:
	pulumi login $(BUCKET_S3)
	pulumi stack init $(STACK) || true
	pulumi config set --stack $(STACK) clusterNumber $(CLUSTERMESH_NUMBER)
	pulumi config set --stack $(STACK) instanceType $(INSTANCE_TYPE)
	pulumi config set --stack $(STACK) poolId $(POOL_ID)
	pulumi config set --stack $(STACK) aws:region $(REGION)
	pulumi up --stack $(STACK) -p $(PULUMI_PARALLEL)

destroy:
	bash ./remove-state.sh
	pulumi down -p $(PULUMI_PARALLEL)

dev0 dev1 dev2 dev3 dev4 dev5 dev6:
	$(MAKE) deploy_stack STACK=$@ POOL_ID=$$(echo $@ | sed 's/dev//') REGION=$(AWS_DEFAULT_REGION)

rec:
	asciinema rec $(AWS_DEFAULT_REGION).cast

gzip:
	gzip $(AWS_DEFAULT_REGION).cast
