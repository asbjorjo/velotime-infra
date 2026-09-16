variable "environment" {
  description = "GitHub Actions deployment environment name; used as the clusters/<environment> folder name for Flux sync."
  type        = string
}

variable "flux_bootstrap_revision" {
  default     = 1
  description = "Revision number to manually trigger a Flux bootstrap re-run."
  type        = number
}

variable "flux_git_username" {
  description = "Username for the flux-system git pull secret (HTTPS basic-auth)."
  type        = string
}

variable "flux_git_token" {
  description = "GitHub PAT with read access to this repo, used as the flux-system git pull secret (HTTPS basic-auth)."
  type        = string
  sensitive   = true
}
