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

The `flux-bootstrap` workflow additionally accepts `AZURE_CLIENT_ID`, the non-sensitive client ID used by the `external-secrets` `azure-keyvault` `ClusterSecretStore` (see [`clusters/development/external-secrets-crs/clustersecretstore.yaml`](clusters/development/external-secrets-crs/clustersecretstore.yaml)). When it is unset, `flux-bootstrap` skips creating the `external-secrets-azure-config` authentication Secret in `flux-system`. This service principal needs permission to read secrets from the configured Key Vault.

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

### Development manifests

Each Flux Kustomization has its own directory under [`clusters/development/`](clusters/development/).
The directory contains `flux-kustomization.yaml` (the Flux reconciliation definition) and,
for local resources, `kustomization.yaml` plus the manifests and patches it builds.
The [development root](clusters/development/kustomization.yaml) includes only the Flux
definitions and the FluxInstance, not the component resource builds. Keep
`flux-kustomization.yaml` out of each component's `kustomization.yaml` to avoid
self-reconciliation. Components sourced from upstream Git repositories keep their
upstream paths and any associated source definition in their component directory.

Validate the root with `kubectl kustomize clusters/development`, and validate local
components separately with `kubectl kustomize clusters/development/<component>`.

### Development Keycloak Realm And Clients

The development realm is initialized by
[`keycloak-realm`](clusters/development/keycloak-realm/keycloakrealmimport.yaml).
It imports realm settings, roles, shared token scopes and a public-client PKCE policy,
but no users or client definitions. The baseline is the application's
[`velotime-realm.json`](https://github.com/asbjorjo/VeloTimer/blob/8e5b046df98666355d2351e157e794854b79135b/config/keycloak/realms/velotime-realm.json),
without its test account or wildcard redirects. Built-in scopes are explicitly
preserved alongside `velotime:all`; the shared scope supplies the exact API audience
`https://development.veloti.me`, subject, realm roles and client-role claims even
when a service requests a token without specifying scopes.

[`keycloak-clients`](clusters/development/keycloak-clients/kustomization.yaml)
manages clients separately using the operator's `KeycloakOIDCClient` v2alpha1 API.
The pinned Keycloak/operator release is `26.7.4`. Client management requires the
**experimental** `client-admin-api:v2` feature, enabled in the Keycloak CR.

| Client ID | Flow | Vault Secret |
| --- | --- | --- |
| `velotime.webui` | Public authorization code with S256 PKCE | None |
| `velotime.users.migration` | Client credentials | `velotime-migration-users-secret` |
| `velotime.statistics.processor` | Client credentials | `velotime-statistics-secret` |
| `velotime.timing.processor` | Client credentials | `velotime-timing-secret` |

The WebUI only allows `https://development.veloti.me/signin-oidc` and
`https://development.veloti.me/signout-callback-oidc` redirects, with
`https://development.veloti.me` as its web origin. Its authority is
`https://auth.development.veloti.me/realms/velotime`. Implicit and password grants
are disabled. Processor accounts receive no administrator roles. The migration
account receives the `velotime-users-migration` composite realm role, combining
`timing-admin`, `statistics-admin`, and the `realm-management` client's
`query-users`/`manage-users` roles. These grants do not make ordinary users admins.
Social identity providers and SMTP are not provisioned here; configure any required
providers before migrating users with linked external accounts.

#### First Deployment Prerequisites

Populate all three application client secrets above and these two additional,
independent random secrets in the development Azure Key Vault before reconciling:

- `keycloak-bootstrap-admin-client-secret`: temporary master-realm bootstrap service account.
- `keycloak-operator-client-secret`: permanent operator service account.

`keycloak-realm-secrets` mirrors these values into the `keycloak` namespace.
The bootstrap and permanent Kubernetes Secrets are `keycloak-bootstrap-admin`
and `keycloak-admin`, with fixed client IDs `velotime-bootstrap-admin` and
`velotime-operator` respectively. The operator reads `client-id`/`client-secret`
from `keycloak-admin`. Application workloads keep their existing secrets in
the `velotime` namespace; no secret values are committed to Git.

**This automatic bootstrap requires a new Keycloak database without a master realm.**
`spec.bootstrapAdmin.service` is ignored once the master realm exists. Do not delete
or reset an existing database to satisfy this requirement; use a separately reviewed
admin recovery/provisioning procedure for an already-initialized installation.

Flux applies `keycloak-realm-secrets`, then Keycloak, then the realm import, then
`keycloak-admin-bootstrap`, then `keycloak-clients`. Application deployment and
migration wait for successful client reconciliation. The bootstrap Job uses the
temporary account to create the permanent account in `master`, granting only the
Velotime management client's `manage-clients`, `view-clients`, `manage-users`,
`view-users`, and `manage-realm` roles. It grants no master-realm administration
or permission to create other realms. It verifies permanent API access before
deleting the temporary account. A retry works after cleanup using permanent
credentials; failed verification retains temporary access. Retained completed
Jobs are not periodically rerun. A changed bootstrap script replaces its Job via
the Flux force annotation; it must remain idempotent.

The operator account is not a human master administrator. Establish an independent,
secure recovery procedure before removing bootstrap access. If master administration
is later needed, follow Keycloak's
[admin recovery guide](https://www.keycloak.org/server/bootstrap-admin-recovery);
the recovery command requires all Keycloak nodes to be stopped.

#### Reconciliation And Verification

`KeycloakRealmImport` creates a realm only once: edits do not update an existing
realm or delete it. Keep the import CR managed by Flux to retain its completion
status and avoid recreating a tracked resource through manual cleanup. Changes to
realm settings, policies, scopes or composite roles after import need a separately
reviewed update procedure, not a realm deletion/reimport.

Client CR changes are reconciled by the operator. Referenced client secrets are
polled, allowing vault-backed secret rotation; coordinate this with the existing
application ExternalSecrets' one-hour refresh and workload restarts. Do not rotate
secrets in the Admin UI or mutate operator-managed clients through the Admin API.
The operator does not continuously detect external edits. **Removing a client CR
from Git deletes the live Keycloak client through Flux pruning and its finalizer.**

The permanent operator credential is different: changing its vault secret alone
does not rotate its master-realm client. The completed bootstrap Job does not run
on secret refresh. Coordinate that credential's rotation using an authorized admin
session, the vault value, and the operator; never remove the last working credential.
Keep the bootstrap secret available for retry mounts, but its deleted account
cannot authenticate. Changing it will not recreate an account in an existing master realm.

Run the bootstrap safety tests with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s clusters/development/keycloak-admin-bootstrap -p '*_test.py' -v
```

Build the four new components separately as well as the development root. After
deployment to the explicitly selected development context, verify ExternalSecrets
are Ready, the realm import reports `Done=True`, the bootstrap Job is Complete,
and every client reports current `observedGeneration`, nonempty `uuid`/`hash`, and
`HasErrors=False`. The Flux health expressions reject missing or stale client status.
Check realm discovery at
`https://auth.development.veloti.me/realms/velotime/.well-known/openid-configuration`,
then test WebUI login/logout and fresh service tokens' exact issuer, audience,
subject and permitted/forbidden API operations. Never print secrets or tokens in
logs, and do not run user-data migrations solely as an authentication test.
