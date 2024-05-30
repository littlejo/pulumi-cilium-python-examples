# Requirement

## Pulumi

```
curl -fsSL https://get.pulumi.com | sh
```

## AWS CLI

* https://aws.amazon.com/cli/

# Deploy EKS and Cilium Cluster Mesh

```
pulumi up
```

* It also deploy on 2 AZs:
* one vpc by cluster (and one nat gateway by VPC)
* one transit gateway (with vpc attachments)

## Number of EKS clusters

By default, you deployed 2 clusters eks.

But if you want to only have 5 clusters:

```
pulumi config set clusterNumber 5
pulumi up
```

## Kubeconfig

Once deployed:

```
export KUBECONFIG=kubeconfig.yaml
```

# Example with 5 clusters

![Example of deployment of cilium on AWS EKS](img/eks-clustermesh.gif)
