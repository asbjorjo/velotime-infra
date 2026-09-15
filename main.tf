module "network" {
  source = "./network"

  basename         = var.basename
  zone             = var.zone
  gateway_plan     = var.network_gateway_plan
  ip_network_range = var.ip_network_range
}

module "cluster" {
  source = "./cluster"

  basename         = var.basename
  store_kubeconfig = false
  zone             = var.zone
  plan             = var.cluster_plan
  node_plan        = var.cluster_node_plan

  nodes = 1

  network = module.network.network_id
  gateway = module.network.gateway_id

  ssh_keys        = var.ssh_keys
  admin_ip_filter = var.admin_ip_filter
}

# module "cache" {
#   source = "./cache"

#   basename = var.basename
#   network  = module.network.network_id
#   zone     = var.zone
#   plan     = var.cache_plan

#   admin_ip_filter = var.admin_ip_filter
#   db_username     = var.cache_db_username
#   db_password     = var.cache_db_password
# }

# module "database" {
#   source = "./database"

#   basename = var.basename
#   network  = module.network.network_id
#   zone     = var.zone
#   plan     = var.database_plan

#   username = var.database_username
#   password = var.database_password
# }

module "flux_operator_bootstrap" {
  source  = "controlplaneio-fluxcd/flux-operator-bootstrap/kubernetes"
  version = "0.8.0"

  depends_on = [module.cluster]

  revision = var.flux_bootstrap_revision

  gitops_resources = {
    instance_yaml = file("${path.module}/clusters/${var.environment}/flux-system/flux-instance.yaml")
  }

  # Reconciled by Terraform on every apply; only a hash is persisted to state, never the token.
  managed_resources = {
    secrets_yaml = <<-YAML
      apiVersion: v1
      kind: Secret
      metadata:
        name: flux-system
      type: kubernetes.io/basic-auth
      stringData:
        username: ${var.flux_git_username}
        password: ${var.flux_git_token}
      YAML
  }
}
