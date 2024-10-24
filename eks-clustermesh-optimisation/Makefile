DIR=/root/pulumi-cilium-python-examples/eks-clustermesh-optimisation
PULUMI_PARALLEL=12
CLUSTERMESH_PARALLEL=2
CLUSTERMESH_NUMBER=8

init:
	pulumi login --local
	pulumi stack init dev
	pulumi config set --stack dev clusterNumber $(CLUSTERMESH_NUMBER)
	pulumi config set --stack dev parallel $(CLUSTERMESH_PARALLEL)
	
plan:
	pulumi preview

apply:
	pulumi up -p $(PULUMI_PARALLEL)

check:
	export KUBECONFIG=$(DIR)/kubeconfig.yaml
	check-cilium.sh

destroy:
	bash ./remove-state.sh
	pulumi down -p $(PULUMI_PARALLEL)
