output "database_id" {
  value = upcloud_managed_database_postgresql.instance.id
}

output "database_host" {
  value = upcloud_managed_database_postgresql.instance.service_host
}

output "database_port" {
  value = upcloud_managed_database_postgresql.instance.service_port
}