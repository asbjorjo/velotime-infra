variable "basename" {
  default     = "velotime-dev"
  description = "Instance base name."
  type        = string
}

variable "zone" {
  description = "UpCloud zone for resource provisioning."
  type        = string
}

variable "network_gateway_plan" {
  default     = "essentials"
  description = "UpCloud plan for the NAT gateway."
  type        = string
}

variable "cluster_plan" {
  default     = "dev-md"
  description = "UpCloud plan for the Kubernetes cluster control plane."
  type        = string
}

variable "cluster_node_plan" {
  default     = "CLOUDNATIVE-1xCPU-4GB"
  description = "UpCloud plan for the Kubernetes worker nodes."
  type        = string
}

variable "cache_plan" {
  default     = "1x1xCPU-1GB"
  description = "UpCloud plan for the cache instance."
  type        = string
}

variable "database_plan" {
  default     = "1x1xCPU-1GB-10GB"
  description = "UpCloud plan for the database instance."
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