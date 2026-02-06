module "network" {
    source = "./network"

  basename = var.basename
}
module "cluster" {
  source = "./cluster"

  basename         = var.basename
  store_kubeconfig = true
  zone             = var.zone

  network = module.network.network_id
  gateway = module.network.gateway_id
}

module "database" {
  source = "./database"

  basename = var.basename
  network = module.network.network_id
}
