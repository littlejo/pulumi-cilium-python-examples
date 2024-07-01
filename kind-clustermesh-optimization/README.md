# Install pulumi

```
curl -fsSL https://get.pulumi.com | sh
```

# Deploy cilium

```
pulumi up
```

## Number of clusters

By default the number of clusters is 4.

But if you want to only test with 10 clusters:

```
pulumi config set clusterNumber 10
pulumi up
```

It should work with more than 200 but i never tested because it needs a good computer :)

# Example

![Example of deployment of cilium clustermesh on 10 clusters](img/clustermesh-10.gif)
