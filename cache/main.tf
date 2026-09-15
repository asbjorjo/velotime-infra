# MySQL managed database with additional logical database: example2_db 
resource "upcloud_managed_database_valkey" "instance" {
  name  = "${var.basename}-cache"
  plan  = var.plan
  zone  = var.zone
  title = "Instance cache"

  properties {
    public_access = false
    ip_filter     = var.admin_ip_filter
  }

  network {
    family = "IPv4"
    name   = "${var.basename}-net"
    type   = "private"
    uuid   = var.network
  }
}

resource "upcloud_managed_database_user" "velotime" {
  service  = upcloud_managed_database_valkey.instance.id
  username = var.db_username
  password = var.db_password

  valkey_access_control {
    keys       = ["*"]
    categories = ["+@all", "-@admin", "-@dangerous"]
    commands   = ["-keys", "-scan", "-flushdb", "-flushall", "-debug"]
    channels   = ["*"]
  }
}