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

variable "ip_network_range" {
  default = "172.16.2.0/24"
  description = "CIDR range used by the cluster SDN network."
  type = string
}