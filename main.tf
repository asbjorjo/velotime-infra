module "network" {
  source = "./network"

  basename = var.basename
}

module "cluster" {
  source = "./cluster"

  basename         = var.basename
  store_kubeconfig = false
  zone             = var.zone

  nodes = 2

  network = module.network.network_id
  gateway = module.network.gateway_id
}

module "cache" {
  source = "./cache"

  basename = var.basename
  network  = module.network.network_id
  zone     = var.zone
}

module "database" {
  source = "./database"

  basename = var.basename
  network  = module.network.network_id
  zone     = var.zone
}

# module "velotime" {
#   source = "./application"

#   cluster_id = module.cluster.cluster_id
#   database_id = module.database.database_id
#   database_host = module.database.database_host
#   database_port = module.database.database_port
#   velotime_version = "latest"
# }
