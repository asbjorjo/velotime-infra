variable "basename" {
  description = "Instance base name derived from the deployment environment."
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

variable "ip_network_range" {
  default     = "172.16.2.0/24"
  description = "CIDR range used by the cluster SDN network."
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

variable "cluster_node_count" {
  default     = 3
  description = "Number of Kubernetes worker nodes."
  type        = number
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
  default     = "velotime"
  sensitive   = true
}

variable "database_username" {
  description = "Username for the database user."
  type        = string
  default     = "velotime"
  sensitive   = true
}

variable "keycloak_database_username" {
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

variable "azure_location" {
  description = "Azure region for the Key Vault resource group."
  type        = string
}

variable "azure_eso_object_id" {
  description = "Azure AD object id of the External Secrets service principal, granted read-only access to the Key Vault."
  type        = string
}