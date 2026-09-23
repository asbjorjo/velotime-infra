output "database_id" {
  value = upcloud_managed_database_valkey.instance.id
}

output "database_host" {
  value = upcloud_managed_database_valkey.instance.service_host
}

output "database_port" {
  value = upcloud_managed_database_valkey.instance.service_port
}

output "database_username" {
  value     = upcloud_managed_database_user.velotime.username
  sensitive = true
}

output "database_password" {
  value     = upcloud_managed_database_user.velotime.password
  sensitive = true
}