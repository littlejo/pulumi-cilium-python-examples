# Install pulumi

```
curl -fsSL https://get.pulumi.com | sh
```

# Install dependancies

## Python libraries

```
pulumi install
```

## Create a cluster kubernetes

```
kind create cluster --config kind.yaml
cat kind.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
- role: worker
networking:
  disableDefaultCNI: true
```

# Deploy cilium

```
pulumi up
```
