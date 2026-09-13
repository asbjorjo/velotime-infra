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