output "database_id" {
  value = upcloud_managed_database_postgresql.instance.id
}

output "database_host" {
  value = upcloud_managed_database_postgresql.instance.service_host
}

output "database_port" {
  value = upcloud_managed_database_postgresql.instance.service_port
}

output "database_name" {
  value = upcloud_managed_database_logical_database.velotime_db.name
}

output "database_admin_username" {
  value     = upcloud_managed_database_postgresql.instance.service_username
  sensitive = true
}

output "database_admin_password" {
  value     = upcloud_managed_database_postgresql.instance.service_password
  sensitive = true
}

output "database_username" {
  value     = upcloud_managed_database_user.velotime.username
  sensitive = true
}

output "database_password" {
  value     = upcloud_managed_database_user.velotime.password
  sensitive = true
}

output "keycloak_database_name" {
  value = upcloud_managed_database_logical_database.keycloak_db.name
}

output "keycloak_database_username" {
  value     = upcloud_managed_database_user.keycloak.username
  sensitive = true
}

output "keycloak_database_password" {
  value     = upcloud_managed_database_user.keycloak.password
  sensitive = true
}

output "database_admin_database" {
  value = upcloud_managed_database_postgresql.instance.primary_database
}
