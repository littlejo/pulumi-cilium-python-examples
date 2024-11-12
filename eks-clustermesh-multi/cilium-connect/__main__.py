import pulumi
import pulumi_aws as aws_tf
import littlejo_cilium as cilium
import yaml

class Cilium:
   def __init__(self, k8s_name, config_path=None, parent=None, depends_on=[], context=None):
       self.k8s_name = k8s_name
       self.provider = cilium.Provider(f"cilium-provider-{k8s_name}", config_path=config_path, context=context, opts=pulumi.ResourceOptions(parent=parent, depends_on=depends_on))

   def deploy(self, version, sets=None):
       self.deploy = cilium.Install(f"cilium-install-{self.k8s_name}",
         sets=sets,
         version=version,
         opts=pulumi.ResourceOptions(parent=self.provider, providers=[self.provider]),
      )

   def cmesh_enable(self, service_type):
       self.cmesh = cilium.Clustermesh(f"cilium-cmesh-enable-{self.k8s_name}", service_type=service_type, opts=pulumi.ResourceOptions(parent=self.deploy, providers=[self.provider])),

   def cmesh_connection(self, name, destination_contexts=None, connection_mode="mesh", parallel=2, depends_on=[]):
       self.cmesh_connect = cilium.ClustermeshConnection(f"cilium-cmesh-connect-{name}",
                                                         destination_contexts=destination_contexts,
                                                         connection_mode=connection_mode,
                                                         parallel=parallel,
                                                         opts=pulumi.ResourceOptions(parent=self.provider,
                                                                                     depends_on=depends_on,
                                                                                     providers=[self.provider])
                                                        )
   def get_cmesh_enable(self):
       return self.cmesh

def get_config_value(key, default=None, value_type=str):
    try:
        value = config.require(key)
        return value_type(value)
    except pulumi.ConfigMissingError:
        return default
    except ValueError:
        print(f"Warning: Could not convert config '{key}' to {value_type.__name__}, using default.")
        return default

def merge_kubeconfigs(files, output_path):
    merged_config = {
        "apiVersion": "v1",
        "kind": "Config",
        "preferences": {},
        "clusters": [],
        "contexts": [],
        "users": [],
        "current-context": None,
    }

    for i, f in enumerate(files):
        config = yaml.safe_load(f)

        merged_config["clusters"].extend(config.get("clusters", []))
        merged_config["contexts"].extend(config.get("contexts", []))
        merged_config["users"].extend(config.get("users", []))

        if i == 0 and "current-context" in config:
            merged_config["current-context"] = config["current-context"]

    with open(output_path, 'w') as f_out:
        yaml.safe_dump(merged_config, f_out, default_flow_style=False)

#Main
config = pulumi.Config()

parallel = get_config_value("parallel", 3, int)
cluster_number = get_config_value("clusterNumber", 4, int)
vpc_number = get_config_value("vpcNumber", 2, int)
cluster_ids = list(range(0, cluster_number))
stack_prefix = get_config_value("stackPrefix", "eks-cilium-cmesh/dev")
cluster_ids = list(range(cluster_id_first, cluster_number + cluster_id_first))

stacks = [ f"organization/{stack_prefix}{id}" for id in list(range(vpc_number)) ]

kubeconfig = "kubeconfig-py.yaml"

output_data = [pulumi.StackReference(stack).get_output("kubeconfig") for stack in stacks]

def setup_cilium(configs):
    merge_kubeconfigs(configs, kubeconfig)

    cilium_connect = Cilium(f"cmesh", config_path=kubeconfig, context=f"eksCluster-0")
    cilium_connect.cmesh_connection(f"cmesh-connect", parallel=parallel, destination_contexts=[f"eksCluster-{i}" for i in cluster_ids if i != 0])

pulumi.Output.all(*output_data).apply(setup_cilium)
