# Requirement

## Pulumi

```
curl -fsSL https://get.pulumi.com | sh
```

## AWS CLI

* https://aws.amazon.com/cli/

# Deploy EKS and Cilium

```
pulumi up
```

## AZs

By default, the availability zones are REGIONa and REGIONb.

But if you want to have a, b and c:

```
pulumi config set AZLetters a,b,c
pulumi up
```

## Kubeconfig

Once deployed, to get kubeconfig:

```
pulumi stack output kubeconfig > kubeconfig.json
export KUBECONFIG=kubeconfig.json
```

# Example

![Example of deployment of cilium on AWS EKS](img/eks.gif)
