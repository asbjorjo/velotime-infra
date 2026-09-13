output "database_id" {
  value = upcloud_managed_database_valkey.instance.id
}

output "database_host" {
  value = upcloud_managed_database_valkey.instance.service_host
}

output "database_port" {
  value = upcloud_managed_database_valkey.instance.service_port
}