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

# Azure DNS credentials for external-dns (see clusters/<environment>/external-dns/helmrelease.yaml).
# Left unset (null) to skip creating the external-dns-azure-config Secret for environments that don't wire external-dns yet.
variable "azure_dns_resource_group" {
  description = "Azure resource group containing the Azure DNS zone that external-dns manages; must match the external-dns HelmRelease's azure-resource-group extraArg."
  type        = string
  default     = null
}

variable "azure_tenant_id" {
  description = "Azure AD tenant ID for the external-dns service principal."
  type        = string
  default     = null
}

variable "azure_subscription_id" {
  description = "Azure subscription ID containing the Azure DNS zone."
  type        = string
  default     = null
}

variable "azure_client_id" {
  description = "Client (application) ID of the external-dns Azure service principal."
  type        = string
  default     = null
}

variable "azure_client_secret" {
  description = "Client secret of the external-dns Azure service principal."
  type        = string
  sensitive   = true
  default     = null
}
