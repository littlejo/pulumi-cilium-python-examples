CLUSTERMESH_NUMBER=4
INSTANCE_TYPE="t4g.medium"

cilium-connect:
	pulumi login --local
	#pulumi stack init cilium-connect
	pulumi config set --stack cilium-connect clusterNumber $(CLUSTERMESH_NUMBER)
	pulumi up --stack cilium-connect
