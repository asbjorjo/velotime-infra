# MySQL managed database with additional logical database: example2_db 
resource "upcloud_managed_database_postgresql" "instance" {
  name  = "${var.basename}-pg"
  plan  = var.plan
  zone  = var.zone
  title = "Instance database"

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

resource "upcloud_managed_database_user" "velotime" {
  service  = upcloud_managed_database_postgresql.instance.id
  username = var.username
  password = var.password

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