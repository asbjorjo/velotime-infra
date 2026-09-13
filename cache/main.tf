# MySQL managed database with additional logical database: example2_db 
resource "upcloud_managed_database_valkey" "instance" {
  name = "velotime-dev-cache"
  plan = "1x1xCPU-1GB"
  zone = "fi-hel1"
  title = "Instance cache"

  properties {
    public_access = true
    ip_filter = [ "51.174.73.141/32" ]
  }

  network {
    family = "IPv4"
    name = "velotime-dev-net"
    type = "private"
    uuid = var.network
  }
}

resource "upcloud_managed_database_user" "velotime" {
  service = upcloud_managed_database_valkey.instance.id
  username = "velotime"
  password = "velotime"

  valkey_access_control {
    keys = ["*"]
    categories = [ "+@all", "-@admin", "-@dangerous" ]
    commands = ["-keys", "-scan", "-flushdb", "-flushall", "-debug"]
    channels = [ "*" ]
  }
}