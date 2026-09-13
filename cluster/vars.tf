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

variable "nodes" {
  default = 3
  type = number
}

variable "store_kubeconfig" {
  default     = true
  description = "If set to `true`, store kubeconfig as a file with `local_file` to module path."
  type        = bool
}

variable "gateway" {
  description = "Instance gateway id."
  type = string
}

variable "network" {
  description = "Instance network id."
  type = string
}