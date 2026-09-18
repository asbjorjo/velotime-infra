module "flux_operator_bootstrap" {
  source  = "controlplaneio-fluxcd/flux-operator-bootstrap/kubernetes"
  version = "0.8.0"

  revision = var.flux_bootstrap_revision

  gitops_resources = {
    instance_yaml = file("${path.module}/../clusters/${var.environment}/flux-system/flux-instance.yaml")
  }

  # Reconciled by Terraform on every apply; only a hash is persisted to state, never the token.
  managed_resources = {
    secrets_yaml = join("\n---\n", compact([
      yamlencode({
        apiVersion = "v1"
        kind       = "Secret"
        metadata = {
          name = "flux-system"
        }
        type = "Opaque"
        stringData = {
          username = var.flux_git_username
          password = var.flux_git_token
        }
      }),
      local.external_secrets_azure_enabled ? yamlencode({
        apiVersion = "v1"
        kind       = "Secret"
        metadata = {
          name = "external-secrets-azure-config"
        }
        type = "Opaque"
        stringData = {
          clientId     = var.azure_client_id
          clientSecret = var.azure_client_secret
        }
      }) : "",
    ]))
  }

  debug_on_failure = true
}

locals {
  external_secrets_azure_enabled = var.azure_client_id != null && var.azure_client_id != ""
}

removed {
  from = kubernetes_namespace_v1.external_dns

  lifecycle {
    destroy = false
  }
}

removed {
  from = kubernetes_secret_v1.external_dns_azure_config

  lifecycle {
    destroy = false
  }
}
