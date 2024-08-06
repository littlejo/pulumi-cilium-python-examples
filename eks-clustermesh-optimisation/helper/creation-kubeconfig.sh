number=$1
export KUBECONFIG=kubeconfig-eksCluster-$number.yaml
export serviceaccount=admin-$number
namespace=default

kubectl create sa $serviceaccount -n $namespace
kubectl create clusterrolebinding $serviceaccount --serviceaccount=$namespace:$serviceaccount --clusterrole=cluster-admin

kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: $serviceaccount
  namespace: $namespace
  annotations:
    kubernetes.io/service-account.name: $serviceaccount
type: kubernetes.io/service-account-token
EOF

token=$(kubectl get secret $serviceaccount -n $namespace -o "jsonpath={.data.token}" | base64 -d)
ca=$(kubectl get secret $serviceaccount -n $namespace -o "jsonpath={.data.ca\.crt}" | base64 -d)
ca_crt="$(mktemp)"; echo "$ca" > $ca_crt
cluster=eksCluster-$number
context=$cluster
server=$(kubectl config view -o "jsonpath={.clusters[].cluster.server}")

export KUBECONFIG=./kubeconfig-sa-$number
kubectl config set-credentials $serviceaccount --token="$token" >/dev/null
kubectl config set-cluster "$cluster" --server="$server" --certificate-authority="$ca_crt" --embed-certs >/dev/null
kubectl config set-context "$context" --cluster="$cluster" --namespace="$namespace" --user="$serviceaccount" >/dev/null
kubectl config use-context "$context" >/dev/null
