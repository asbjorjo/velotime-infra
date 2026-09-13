variable "basename" {
  default     = "velotime-dev"
  description = "Instance base name."
  type        = string
}

variable "zone" {
  default     = "fi-hel1"
  description = "UpCloud zone for resource provisioning."
  type        = string
}

variable "ssh_keys" {
  description = "Authorized SSH public keys for cluster nodes."
  type        = list(string)
  sensitive   = true
}

variable "admin_ip_filter" {
  description = "IP addresses/CIDRs allowed to access the cluster control plane and cache instance."
  type        = list(string)
  sensitive   = true
}

variable "cache_db_username" {
  description = "Username for the cache database user."
  type        = string
  sensitive   = true
}

variable "cache_db_password" {
  description = "Password for the cache database user."
  type        = string
  sensitive   = true
}

variable "database_username" {
  description = "Username for the database user."
  type        = string
  sensitive   = true
}

variable "database_password" {
  description = "Password for the database user."
  type        = string
  sensitive   = true
}