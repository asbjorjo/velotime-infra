variable "basename" {
  default     = "velotime"
  description = "Basename to use when naming resources created by this configuration."
  type        = string
}

variable "zone" {
  default     = "fi-hel1"
  description = "UpCloud zone for resource provisioning."
  type        = string
}

variable "network" {
  description = "Instance network id."
  type        = string
}

variable "admin_ip_filter" {
  description = "IP addresses/CIDRs allowed to access the cache instance."
  type        = list(string)
  sensitive   = true
}

variable "db_username" {
  description = "Username for the cache database user."
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Password for the cache database user."
  type        = string
  sensitive   = true
}
