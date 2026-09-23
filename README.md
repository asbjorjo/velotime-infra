# Velotime Infrastructure

## GitHub Actions

Workflows use GitHub [deployment environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment):

- Pull requests to `main` or `production` run `tofu -chdir=terraform fmt -check` and `tofu -chdir=flux-bootstrap fmt -check` only.
- Pushes to `main` run the core `terraform/` deployment (development plan and apply, then production plan, then production apply after manual approval). After each environment's core apply succeeds, that environment's `flux-bootstrap/` deployment runs plan and apply automatically.

The core `terraform/` deployment uses the `production-approval` gate. Configure required reviewers on `production-approval` so production apply pauses after a successful production plan. The `flux-bootstrap/` deployment does not require a separate production approval; it runs after the already-approved production core apply succeeds. Keep Terraform variables and secrets on the `development` and `production` environments; if production plan should run automatically, do not put required reviewers on the `production` environment itself.

Each deployment job's GitHub Environment is used as the state bucket name and selects a committed variable file:

- `development`: `terraform/environments/development.tfvars`, `flux-bootstrap/environments/development.tfvars`, and state bucket `development`.
- `production`: `terraform/environments/production.tfvars`, `flux-bootstrap/environments/production.tfvars`, and state bucket `production`.

The core Terraform files define the environment basename, zone, network, and resource plans. The Flux bootstrap files define the environment selected for Flux synchronization and the bootstrap revision. Add matching files in both locations before deploying a new environment.

### Environment Configuration

Configure the following variables in each Terraform GitHub Environment (`development` and `production`):

- `BACKEND_REGION`: The region of the Object Storage bucket (e.g., `europe-1`).
- `BACKEND_ENDPOINT`: The S3-compatible endpoint URL (e.g., `https://spfj4.upcloudobjects.com`).
- `ADMIN_IP_FILTER`: JSON array of allowed IP addresses/CIDRs for admin access, such as `["203.0.113.10/32"]`. Passed as-is to Terraform's `admin_ip_filter` variable, which sets the cluster's `control_plane_ip_filter`. The `flux-bootstrap` workflow separately opens the control-plane API to its own runner's IP for the duration of its run (see [Flux CD Bootstrap](#flux-cd-bootstrap)); it does not modify this variable's persisted value.
- `FLUX_GIT_USERNAME`: Username for Flux's `flux-system` git pull secret. It is passed to Flux bootstrap at runtime.
- `AZURE_TF_CLIENT_ID`: Client ID of the dedicated Terraform service principal used by the `terraform/keyvault` module (authenticates via GitHub Actions OIDC federated credential, no client secret).
- `AZURE_TENANT_ID`: Azure AD tenant ID for that service principal.
- `AZURE_ESO_OBJECT_ID`: Azure AD object ID (not client ID) of the External Secrets service principal (`AZURE_CLIENT_ID` below), granted read-only access to the Key Vault created by `terraform/keyvault`.

The `flux-bootstrap` workflow additionally accepts `AZURE_CLIENT_ID`, the non-sensitive client ID used by the `external-secrets` `azure-keyvault` `ClusterSecretStore` (see `clusters/<environment>/external-secrets/crs/clustersecretstore.yaml`). When it is unset, `flux-bootstrap` skips creating the `external-secrets-azure-config` authentication Secret in `flux-system`. This service principal needs permission to read secrets from the configured Key Vault.

### Secrets

Configure these secrets (at the environment or repository level):

- `UPCLOUD_TOKEN`: UpCloud API token used by the provider.
- `UPCLOUD_S3_ACCESS_KEY_ID`: UpCloud Object Storage access key ID.
- `UPCLOUD_S3_SECRET_ACCESS_KEY`: UpCloud Object Storage secret access key.
- `CLUSTER_SSH_KEYS`: SSH public keys for cluster access.
- `AZURE_SUBSCRIPTION_ID`: Azure subscription for the `terraform/keyvault` module's resource group and Key Vault.

The `flux-bootstrap` workflow additionally requires:

- `FLUX_GIT_TOKEN`: GitHub PAT with read access to this repo, used as the Flux `flux-system` git pull secret.
- `UPCLOUD_TOKEN`, `UPCLOUD_S3_ACCESS_KEY_ID`, `UPCLOUD_S3_SECRET_ACCESS_KEY` (shared with the core deployment above).
- `AZURE_CLIENT_SECRET`: Client secret paired with `AZURE_CLIENT_ID`, used by the External Secrets Operator to authenticate to Azure Key Vault.

For each environment that deploys external-dns, populate these secrets in the vault referenced by its `azure-keyvault` `ClusterSecretStore`:

- `external-dns-azure-tenant-id`: Azure AD tenant ID for the external-dns service principal.
- `external-dns-azure-subscription-id`: Subscription containing the Azure DNS zone.
- `external-dns-azure-resource-group`: Resource group containing the Azure DNS zone; it must match the HelmRelease's `azure-resource-group` argument.
- `external-dns-azure-client-id`: Client ID of the external-dns service principal.
- `external-dns-azure-client-secret`: Client secret of the external-dns service principal.

The external-dns service principal needs `Reader` on the resource group and `Contributor` or `DNS Zone Contributor` on the DNS zone. Flux first reconciles the dedicated `external-dns-namespace` Kustomization, then the ExternalSecret renders these values into the `external-dns/external-dns-azure-config` Secret's `azure.json` key. The external-dns Kustomization waits for that Secret before reconciling its HelmRelease; OpenTofu no longer creates the namespace or configuration Secret.

### Azure Key Vault (`terraform/keyvault`)

The core `terraform/` deployment provisions a per-environment Azure resource group (`velotime-infra-<basename>`) and Key Vault (`velotime-<basename>`), and writes the cache/database host, port, username, and Terraform-generated password into it as `velotime-cache-*`/`velotime-database-*` secrets. It also creates a `keycloak` logical database with its own user, then writes those connection values as `keycloak-database-host`, `keycloak-database-port`, `keycloak-database-name`, `keycloak-database-user`, and `keycloak-database-password` — the same secret names the `external-secrets` `azure-keyvault` `ClusterSecretStore` reads from. Database usernames default to `velotime` for cache and application database access and `keycloak` for Keycloak database access. Database passwords are generated inside the Terraform modules and are not passed through GitHub environment secrets. Authentication uses `AZURE_TF_CLIENT_ID`/`AZURE_TENANT_ID`/`AZURE_SUBSCRIPTION_ID` via GitHub Actions OIDC (`ARM_USE_OIDC`); a matching federated credential must exist on that app registration in Azure AD for each environment (subject `repo:<org>/<repo>:environment:development`/`:environment:production`). The module grants itself `Key Vault Secrets Officer` and grants the existing `AZURE_ESO_OBJECT_ID` principal `Key Vault Secrets User`.

The derived Object Storage buckets must exist before their workflows run. Object Storage credentials should have read and write access to the respective state bucket and the `velotime-infra/terraform.tfstate` state key. Migrate existing state, including state in legacy buckets such as `velotime-tfstate-dev`, to the derived bucket before the apply workflow runs.

Pull requests from forks run the same format check as other pull requests and do not receive state-backed plans.

Configure the `production-approval` GitHub Environment with required reviewers only. It does not need Terraform variables or secrets.

## Flux CD Bootstrap

The `flux-bootstrap/` root module is a separate Terraform deployment from `terraform/`, with its
own state (`velotime-infra/flux-bootstrap.tfstate` in the same environment bucket). It bootstraps
[Flux Operator](https://fluxcd.control-plane.io/operator/) on the cluster created by the
`terraform/` deployment, via the
[`flux-operator-bootstrap`](https://github.com/controlplaneio-fluxcd/terraform-kubernetes-flux-operator-bootstrap)
module. It reads the `FluxInstance` manifest from
`clusters/<environment>/flux-system/flux-instance.yaml`, where `<environment>` is loaded from
the matching `flux-bootstrap/environments/<environment>.tfvars` file — a matching manifest must
exist for each environment before that environment's plan or apply can succeed. The `flux-system` git pull secret used by
`sync.pullSecret` is provisioned from the `FLUX_GIT_TOKEN` secret above and reconciled on
every apply.

Since `flux-bootstrap/` has no `upcloud` provider, its `helm` and `kubernetes` providers read a
kubeconfig file (`flux-bootstrap/kubeconfig.yml`, git-ignored) that the `flux-bootstrap-apply.yml`
workflow fetches at runtime with `upctl kubernetes config <basename>-cluster`, after temporarily
allowing the runner's IP through the cluster's control-plane IP filter with
`upctl kubernetes modify <basename>-cluster --kubernetes-api-allow-ip <runner-ip>`. The cluster
name is assumed to follow the `<basename>-cluster` convention used by the `cluster` module. The
`flux-bootstrap-apply.yml` workflow is called by the `terraform-apply.yml` ("OpenTofu Deploy")
workflow after each environment's core `tofu apply` succeeds.
