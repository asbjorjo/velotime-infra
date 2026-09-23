terraform {
  required_providers {
    upcloud = {
      source  = "UpCloudLtd/upcloud"
      version = ">= 2.11.0"
    }
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.27"
    }
  }
}

# provider "postgresql" {
#   host            = upcloud_managed_database_postgresql.instance.service_host
#   port            = upcloud_managed_database_postgresql.instance.service_port
#   database        = upcloud_managed_database_postgresql.instance.primary_database
#   username        = upcloud_managed_database_postgresql.instance.service_username
#   password        = upcloud_managed_database_postgresql.instance.service_password
#   sslmode         = upcloud_managed_database_postgresql.instance.sslmode
#   connect_timeout = 15
#   superuser       = false
# }