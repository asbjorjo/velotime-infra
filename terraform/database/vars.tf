variable "basename" {
  default     = "velotime"
  description = "Basename to use when naming resources created by this configuration."
  type        = string
}

variable "zone" {
  description = "UpCloud zone for resource provisioning."
  type        = string
}

variable "plan_compute" {
  default     = "rdb.development.1CPU-1GB"
  description = "UpCloud compute shape for the database instance."
  type        = string
}

variable "plan_node_count" {
  default     = 1
  description = "Number of nodes in the database plan."
  type        = number
}

variable "plan_storage_gib" {
  default     = 10
  description = "Database storage per node in GiB."
  type        = number
}

variable "plan_backups" {
  default     = "mini"
  description = "Backup tier for the database plan."
  type        = string
}

variable "network" {
  description = "Instance network id."
  type        = string
}

variable "username" {
  description = "Username for the database user."
  type        = string
  default     = "velotime"
  sensitive   = true
}

variable "keycloak_username" {
  description = "Username for the Keycloak database user."
  type        = string
  default     = "keycloak"
  sensitive   = true
}

variable "termination_protection" {
  description = "Protect resources from deletion and shutdown"
  type        = bool
  default     = false
}
