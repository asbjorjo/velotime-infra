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
