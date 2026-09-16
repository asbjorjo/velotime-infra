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

  nodes = var.cluster_node_count

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
