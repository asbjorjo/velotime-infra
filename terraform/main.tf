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

module "cache" {
  source = "./cache"

  basename = var.basename
  network  = module.network.network_id
  zone     = var.zone
  plan     = var.cache_plan

  admin_ip_filter = var.admin_ip_filter
  db_username     = var.cache_db_username
}

module "database" {
  source = "./database"

  basename = var.basename
  network  = module.network.network_id
  zone     = var.zone
  plan     = var.database_plan

  username = var.database_username

  keycloak_username = var.keycloak_database_username
}

module "keyvault" {
  source = "./keyvault"

  basename                = var.basename
  location                = var.azure_location
  eso_principal_object_id = var.azure_eso_object_id
  termination_protection  = var.termination_protection

  cache_host     = module.cache.database_host
  cache_port     = module.cache.database_port
  cache_username = module.cache.database_username
  cache_password = module.cache.database_password

  database_host     = module.database.database_host
  database_port     = module.database.database_port
  database_username = module.database.database_username
  database_password = module.database.database_password

  keycloak_database_host     = module.database.database_host
  keycloak_database_port     = module.database.database_port
  keycloak_database_name     = module.database.keycloak_database_name
  keycloak_database_username = module.database.keycloak_database_username
  keycloak_database_password = module.database.keycloak_database_password
}
