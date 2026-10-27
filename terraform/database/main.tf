# MySQL managed database with additional logical database: example2_db 
resource "upcloud_managed_database_postgresql" "instance" {
  name                   = "${var.basename}-pg"
  plan_compute           = var.plan_compute
  plan_node_count        = var.plan_node_count
  plan_storage_gib       = var.plan_storage_gib
  plan_backups           = var.plan_backups
  zone                   = var.zone
  title                  = "Instance database"
  termination_protection = var.termination_protection

  labels = {
    managedBy = "terraform"
    project   = var.basename
  }

  properties {
    version = "18"
  }

  network {
    family = "IPv4"
    name   = "${var.basename}-net"
    type   = "private"
    uuid   = var.network
  }
}

resource "random_password" "velotime" {
  length  = 32
  special = false
}

resource "random_password" "keycloak" {
  length  = 32
  special = false
}

resource "upcloud_managed_database_user" "velotime" {
  service  = upcloud_managed_database_postgresql.instance.id
  username = var.username
  password = random_password.velotime.result

  pg_access_control {
    allow_replication = false
  }
}

resource "upcloud_managed_database_user" "keycloak" {
  service  = upcloud_managed_database_postgresql.instance.id
  username = var.keycloak_username
  password = random_password.keycloak.result

  pg_access_control {
    allow_replication = false
  }
}

resource "upcloud_managed_database_logical_database" "velotime_db" {
  service = upcloud_managed_database_postgresql.instance.id
  name    = "velotimedb"
}

resource "upcloud_managed_database_logical_database" "keycloak_db" {
  service = upcloud_managed_database_postgresql.instance.id
  name    = "keycloak"
}

# resource "postgresql_grant" "velotime_database" {
#   database    = upcloud_managed_database_logical_database.velotime_db.name
#   role        = upcloud_managed_database_user.velotime.username
#   object_type = "database"
#   privileges  = ["CONNECT", "CREATE", "TEMPORARY"]

#   depends_on = [
#     upcloud_managed_database_logical_database.velotime_db,
#     upcloud_managed_database_user.velotime,
#   ]
# }

# resource "postgresql_grant" "keycloak_database" {
#   database    = upcloud_managed_database_logical_database.keycloak_db.name
#   role        = upcloud_managed_database_user.keycloak.username
#   object_type = "database"
#   privileges  = ["CONNECT", "CREATE", "TEMPORARY"]

#   depends_on = [
#     upcloud_managed_database_logical_database.keycloak_db,
#     upcloud_managed_database_user.keycloak,
#   ]
# }