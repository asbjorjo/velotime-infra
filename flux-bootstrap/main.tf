module "flux_operator_bootstrap" {
  source  = "controlplaneio-fluxcd/flux-operator-bootstrap/kubernetes"
  version = "0.8.0"

  revision = var.flux_bootstrap_revision

  gitops_resources = {
    instance_yaml = file("${path.module}/../clusters/${var.environment}/flux-system/flux-instance.yaml")
  }

  # Reconciled by Terraform on every apply; only a hash is persisted to state, never the token.
  managed_resources = {
    secrets_yaml = <<-YAML
      apiVersion: v1
      kind: Secret
      metadata:
        name: flux-system
      type: Opaque
      stringData:
        username: ${var.flux_git_username}
        password: ${var.flux_git_token}
      YAML
  }

  debug_on_failure = true
}

locals {
  external_dns_azure_enabled = var.azure_tenant_id != null && var.azure_tenant_id != ""
}

# Namespace is also declared in clusters/<environment>/external-dns/namespace.yaml; Flux adopts it once the
# external-dns Kustomization reconciles, per the module's namespace hand-off behavior.
resource "kubernetes_namespace_v1" "external_dns" {
  count = local.external_dns_azure_enabled ? 1 : 0

  depends_on = [module.flux_operator_bootstrap]

  metadata {
    name = "external-dns"
  }
}

# Consumed by the external-dns HelmRelease's extraVolumes; not managed via managed_resources.secrets_yaml
# because that mechanism only targets the FluxInstance's own namespace (flux-system), not external-dns.
resource "kubernetes_secret_v1" "external_dns_azure_config" {
  count = local.external_dns_azure_enabled ? 1 : 0

  metadata {
    name      = "external-dns-azure-config"
    namespace = kubernetes_namespace_v1.external_dns[0].metadata[0].name
  }

  data = {
    "azure.json" = jsonencode({
      tenantId        = var.azure_tenant_id
      subscriptionId  = var.azure_subscription_id
      resourceGroup   = var.azure_dns_resource_group
      aadClientId     = var.azure_client_id
      aadClientSecret = var.azure_client_secret
    })
  }

  type = "Opaque"
}
