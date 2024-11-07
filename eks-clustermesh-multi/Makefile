PULUMI_PARALLEL=12
CLUSTERMESH_NUMBER=2
INSTANCE_TYPE="t4g.medium"

.PHONY: dev dev2

deploy_stack:
	pulumi login $(BUCKET_S3)
	pulumi stack init $(STACK) || true
	pulumi config set --stack $(STACK) clusterNumber $(CLUSTERMESH_NUMBER)
	pulumi config set --stack $(STACK) instanceType $(INSTANCE_TYPE)
	pulumi config set --stack $(STACK) poolId $(POOL_ID)
	pulumi up --stack $(STACK) -p $(PULUMI_PARALLEL)

dev:
	$(MAKE) deploy_stack STACK=dev POOL_ID=0

dev2:
	$(MAKE) deploy_stack STACK=dev2 POOL_ID=1

dev3:
	$(MAKE) deploy_stack STACK=dev3 POOL_ID=2

dev4:
	$(MAKE) deploy_stack STACK=dev4 POOL_ID=3

dev5:
	$(MAKE) deploy_stack STACK=dev5 POOL_ID=4

dev6:
	$(MAKE) deploy_stack STACK=dev6 POOL_ID=5

dev7:
	$(MAKE) deploy_stack STACK=dev7 POOL_ID=6
