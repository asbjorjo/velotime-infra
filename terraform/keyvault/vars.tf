variable "basename" {
  default     = "velotime"
  description = "Basename to use when naming resources created by this configuration."
  type        = string
}

variable "location" {
  description = "Azure region for the resource group and Key Vault."
  type        = string
}

variable "eso_principal_object_id" {
  description = "Azure AD object id of the External Secrets service principal, granted read-only access to the vault."
  type        = string
}

variable "cache_host" {
  description = "Cache instance host, stored in the vault as velotime-cache-host."
  type        = string
}

variable "cache_port" {
  description = "Cache instance port, stored in the vault as velotime-cache-port."
  type        = string
}

variable "cache_username" {
  description = "Cache admin username, stored in the vault as velotime-cache-username."
  type        = string
  sensitive   = true
}

variable "cache_password" {
  description = "Cache admin password, stored in the vault as velotime-cache-password."
  type        = string
  sensitive   = true
}

variable "database_host" {
  description = "Database instance host, stored in the vault as velotime-database-host."
  type        = string
}

variable "database_port" {
  description = "Database instance port, stored in the vault as velotime-database-port."
  type        = string
}

variable "database_username" {
  description = "Database admin username, stored in the vault as velotime-database-user."
  type        = string
  sensitive   = true
}

variable "database_password" {
  description = "Database admin password, stored in the vault as velotime-database-password."
  type        = string
  sensitive   = true
}

variable "keycloak_database_host" {
  description = "Keycloak database host, stored in the vault as keycloak-database-host."
  type        = string
}

variable "keycloak_database_port" {
  description = "Keycloak database port, stored in the vault as keycloak-database-port."
  type        = string
}

variable "keycloak_database_name" {
  description = "Keycloak database name, stored in the vault as keycloak-database-name."
  type        = string
}

variable "keycloak_database_username" {
  description = "Keycloak database username, stored in the vault as keycloak-database-user."
  type        = string
  sensitive   = true
}

variable "keycloak_database_password" {
  description = "Keycloak database password, stored in the vault as keycloak-database-password."
  type        = string
  sensitive   = true
}

variable "termination_protection" {
  description = "Protect resources from deletion and shutdown"
  type        = bool
  default     = false
}
