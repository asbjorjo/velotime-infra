variable "basename" {
  default     = "velotime"
  description = "Basename to use when naming resources created by this configuration."
  type        = string
}

variable "zone" {
  description = "UpCloud zone for resource provisioning."
  type        = string
}

variable "plan" {
  default     = "1x1xCPU-1GB-10GB"
  description = "UpCloud plan for the database instance."
  type        = string
}

variable "network" {
  description = "Instance network id."
  type        = string
}

variable "username" {
  description = "Username for the database user."
  type        = string
  sensitive   = true
}

variable "password" {
  description = "Password for the database user."
  type        = string
  sensitive   = true
}

variable "keycloak_username" {
  description = "Username for the Keycloak database user."
  type        = string
  sensitive   = true
}

variable "keycloak_password" {
  description = "Password for the Keycloak database user."
  type        = string
  sensitive   = true
}

variable "termination_protection" {
  description = "Protect resources from deletion and shutdown"
  type        = bool
  default     = false
}
