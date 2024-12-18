kubeconfig=$1
namespace=default
cluster_file="$(mktemp)"
context=$cluster

function create_kubeconfig(){
	kubectl config set-credentials $account --token="$token" >/dev/null
	kubectl config set-cluster "$cluster" --server="$server" --certificate-authority="$ca_crt" --embed-certs >/dev/null
	kubectl config set-context "$context" --cluster="$cluster" --namespace="$namespace" --user="$account" >/dev/null
	kubectl config use-context "$context" >/dev/null
}

export KUBECONFIG=$(mktemp)

ca_crt="$(mktemp)"; echo "$ca" | base64 -d > $ca_crt

export token=$(aws eks get-token --cluster-name $cluster | jq -r .status.token)
create_kubeconfig

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

export token=$(kubectl get secret $serviceaccount -n $namespace -o "jsonpath={.data.token}" | base64 -d)
export account=$serviceaccount

export KUBECONFIG=$kubeconfig
create_kubeconfig

kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: cilium-ca
  namespace: kube-system
  labels:
    app.kubernetes.io/managed-by: Helm
  annotations:
    meta.helm.sh/release-name: cilium
    meta.helm.sh/release-namespace: kube-system
data:
  ca.crt: "$crt_cilium"
  ca.key: "$key_cilium"
EOF
