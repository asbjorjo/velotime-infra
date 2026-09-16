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
