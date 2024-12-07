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

log_info() {
  echo "[INFO] $1"
}

export KUBECONFIG=$(mktemp)

ca_crt="$(mktemp)"; echo "$ca" | base64 -d > $ca_crt

token_tmp=""
while [ -z "$token_tmp" ]; do
  token_tmp=$(aws eks get-token --cluster-name $cluster | jq -r .status.token)

  if [ -z "$token_tmp" ]; then
    log_info "aws token not found, retrying..."
    sleep 5
  fi
done

export token=$token_tmp
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

token_tmp=""
while [ -z "$token_tmp" ]; do
  token_tmp=$(kubectl get secret $serviceaccount -n $namespace -o "jsonpath={.data.token}" | base64 -d)

  if [ -z "$token_tmp" ]; then
    log_info "token not found, retrying..."
    sleep 5
  fi
done

export token=$token_tmp
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
