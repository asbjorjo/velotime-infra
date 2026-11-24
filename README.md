# Velotime Infrastructure

## Dependency Updates

[Dependabot](.github/dependabot.yml) checks weekly for GitHub Actions updates,
Terraform/OpenTofu provider and module updates in both deployments and all local
modules, Python test dependencies in `tests/requirements.txt`, and Dev Container
Features in `.devcontainer/devcontainer.json`. Flux HelmRelease chart versions,
Kustomize remote resources, and container images in Kubernetes manifests are not
covered by this configuration and must be maintained separately.

## GitHub Actions

Workflows use GitHub [deployment environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment):

- Pull requests to `main` or `production` run `tofu -chdir=terraform fmt -check` and `tofu -chdir=flux-bootstrap fmt -check` only.
- Pushes to `main` run the core `terraform/` deployment (development plan and apply, then production plan, then production apply after manual approval). After each environment's core apply succeeds, that environment's `flux-bootstrap/` deployment runs plan and apply automatically.

The core `terraform/` deployment uses the `production-approval` gate. Configure required reviewers on `production-approval` so production apply pauses after a successful production plan. The `flux-bootstrap/` deployment does not require a separate production approval; it runs after the already-approved production core apply succeeds. Keep Terraform variables and secrets on the `development` and `production` environments; if production plan should run automatically, do not put required reviewers on the `production` environment itself.

Each deployment job's GitHub Environment is used as the state bucket name and selects a committed variable file:

- `development`: `terraform/environments/development.tfvars`, `flux-bootstrap/environments/development.tfvars`, and state bucket `development`.
- `production`: `terraform/environments/production.tfvars`, `flux-bootstrap/environments/production.tfvars`, and state bucket `production`.

The core Terraform files define the environment basename, zone, network, and resource plans. The Flux bootstrap files define the environment selected for Flux synchronization and the bootstrap revision. Add matching files in both locations before deploying a new environment.

PostgreSQL uses componentized database plans (UpCloud provider >= 5.46.0): `database_plan_compute`, `database_plan_node_count`, `database_plan_storage_gib`, and `database_plan_backups` replace the legacy `database_plan` input. Both environments configure `rdb.development.1CPU-1GB`, one node, 10 GiB of storage per node, and the `mini` backup tier. Review an environment-specific plan before applying this migration to an existing database.

### Environment Configuration

Configure the following variables in each Terraform GitHub Environment (`development` and `production`):

- `BACKEND_REGION`: The region of the Object Storage bucket (e.g., `europe-1`).
- `BACKEND_ENDPOINT`: The S3-compatible endpoint URL (e.g., `https://spfj4.upcloudobjects.com`).
- `ADMIN_IP_FILTER`: JSON array of allowed IP addresses/CIDRs for admin access, such as `["203.0.113.10/32"]`. Passed as-is to Terraform's `admin_ip_filter` variable, which sets the cluster's `control_plane_ip_filter`. The `flux-bootstrap` workflow separately opens the control-plane API to its own runner's IP for the duration of its run (see [Flux CD Bootstrap](#flux-cd-bootstrap)); it does not modify this variable's persisted value.
- `FLUX_GIT_USERNAME`: Username for Flux's `flux-system` git pull secret. It is passed to Flux bootstrap at runtime.
- `AZURE_TF_CLIENT_ID`: Client ID of the dedicated Terraform service principal used by the `terraform/keyvault` module (authenticates via GitHub Actions OIDC federated credential, no client secret).
- `AZURE_TENANT_ID`: Azure AD tenant ID for that service principal.
- `AZURE_ESO_OBJECT_ID`: Azure AD object ID (not client ID) of the External Secrets service principal (`AZURE_CLIENT_ID` below), granted read-only access to the Key Vault created by `terraform/keyvault`.

The `flux-bootstrap` workflow additionally accepts `AZURE_CLIENT_ID`, the non-sensitive client ID used by the `external-secrets` `azure-keyvault` `ClusterSecretStore` (see the [shared store](infrastructure/external-secrets-crs/clustersecretstore.yaml) and [development configuration](clusters/development/infrastructure/external-secrets-crs/clustersecretstore-patch.yaml)). When it is unset, `flux-bootstrap` skips creating the `external-secrets-azure-config` authentication Secret in `flux-system`. This service principal needs permission to read secrets from the configured Key Vault.

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

The external-dns service principal needs `Reader` on the resource group and `Contributor` or `DNS Zone Contributor` on the DNS zone. Within the infrastructure layer, `external-dns-secrets` waits for both `external-dns-namespace` and the shared store (`external-secrets-crs`), then its ExternalSecret renders these values into the `external-dns/external-dns-azure-config` Secret's `azure.json` key. The external-dns Kustomization waits for `external-dns-secrets` before reconciling its HelmRelease; OpenTofu no longer creates the namespace or configuration Secret. The shared store does not depend on external-dns.

### Development database and cache metrics

The development [database collector](clusters/development/database-opentelemetry-collector/)
adds a separate `database-telemetry` OpenTelemetry collector in
`velotime-instrumentation`. Every 30 seconds it scrapes
`http://<database-host>:9273/metrics` and `http://<cache-host>:9273/metrics`,
using the existing `velotime-database-host` and `velotime-cache-host` vault
secrets. Metrics are exported via OTLP to the existing VeloTime telemetry
collector at `telemetry-collector.velotime-instrumentation.svc.cluster.local:4317`,
which forwards them to its configured destination. Its logs, metrics, and traces
pipelines are unchanged.

Before reconciling development, an operator must configure the metrics endpoints
and provision these secrets in the development Azure Key Vault:

- `database-metrics-user` and `database-metrics-password`: database metrics basic auth.
- `cache-metrics-user` and `cache-metrics-password`: cache metrics basic auth.

These four credentials are operator-managed, **not managed by Terraform**, and
must match the endpoints' metrics credentials, not the database/cache login
credentials. The `database-metrics` ExternalSecret reads them through the shared
`azure-keyvault` store into a Kubernetes Secret consumed by the new collector.
Allow the collector's network access to both endpoints on port 9273.
HTTP basic auth sends credentials unencrypted; this configuration intentionally
uses HTTP and requires a trusted network path.

The database collector has its own root-level Flux Kustomization outside the
deployment layers. It waits for the services layer (including the existing
telemetry collector) and checks its own generated Deployment.
No Kustomization depends on database telemetry. Missing metrics secrets or a
failed database collector remain visible on its Kustomization without blocking
services or applications.
After rotating credentials or changing hostnames, wait for the ExternalSecret to
refresh (up to one hour), then restart the collector to reload its environment:

```sh
kubectl --context <development-context> -n velotime-instrumentation \
  rollout restart deployment/database-telemetry-collector
```

### Development node, cluster, and container logs

Two independent, development-only root Flux Kustomizations add a node Collector
DaemonSet and a single-replica cluster-state Collector Deployment. Each waits for
the services layer, checks its generated workload, and has no dependants. The
existing gateway, its external transport, production configuration, and the
database/cache collector are unchanged.

Both new root Kustomizations are committed with `spec.suspend: true`, so Flux
will not create either Collector or its RBAC until the development log paths,
permissions, and duplicate-log inventory have been verified. After completing
the prerequisites below, set `suspend: false` for each Kustomization to begin
the development rollout.

The node Collector uses the Kubernetes Collector distribution pinned to `0.162.0`
(the distribution and component list were verified against the running
development Collector). It collects kubelet node/pod/container/volume metrics,
host CPU, disk, filesystem, memory, and network metrics, and stdout/stderr files
from `/var/log/pods` across namespaces except `velotime`. The cluster Collector
uses the `k8s_cluster` receiver for cluster-state metrics. Both send OTLP to the
existing `telemetry-collector.velotime-instrumentation` service. Requests and
limits are set per Collector. At inspection time, development had two amd64
nodes with one CPU and about 3.7 GiB allocatable memory each. Recheck node capacity and
admission policy before rollout.

**Do not enable the development Flux components until the runtime prerequisites
and duplicate-log inventory below are verified.** The current cluster inspection
confirmed containerd and the kubelet version, but did not inspect node
`/var/log/pods` contents, CRI log formatting, file permissions, or host filesystem
layout. Confirm that these paths and read-only mounts work on every eligible
node, and that policy permits a root-running but non-privileged agent with
read-only host mounts. The agent runs as root only to read host log files; it
drops all Linux capabilities, disables privilege escalation, and has a
read-only root filesystem. The host root and pod-log directory are mounted
read-only. Node-level kubelet/host metrics and logs may be incomplete if these
assumptions do not hold.

The kubeletstats receiver authenticates with its service-account token but skips
server certificate verification because the kubelet uses a private CA. TLS
encryption without identity verification still permits kubelet impersonation,
credential exposure, and metric tampering. The Collector-to-gateway connection
also uses the existing plaintext OTLP transport; the gateway currently forwards
to its existing external endpoint without transport changes. This exposes
cluster-wide log contents and metrics to network observation and modification.
Confirm the destination and network path are trusted before enabling log export.

Filelog starts at the end of files when first discovered and keeps no persistent
checkpoints. A Collector restart can skip log records; bounded in-memory export
queues can also lose data during prolonged backend failure or saturation.
Delivery is not exactly once, and retries can result in duplicates. Collected
log bodies are not redacted: arbitrary application logs can contain credentials,
personal data, or other secrets, and metadata exclusions are not a redaction or
security boundary.

The node Collector always excludes files for its own and the cluster Collector's
generated pods. Other OTLP-log exclusions require an explicit pod-template
annotation:

```yaml
telemetry.velotime.io/otlp-logs: "true"
```

Add it only after confirming that the workload actually emits the same log
events over OTLP and verifying the pod annotation is visible to the Collector.
The current development pod inspection found .NET auto-instrumentation on some
workloads, but did not establish that they emit OTLP logs. The `velotime`
namespace is excluded wholesale; workloads in other namespaces are not
pre-excluded.
Missing Kubernetes metadata is marked on the log resource and does not trigger a
workload exclusion, so duplicates may pass until the metadata or inventory is
corrected. Recheck this inventory whenever workload logging changes.

Before enabling Flux, verify the on-node log paths and permissions, confirm
service-account authorization to kubelet `/stats/summary` and the Kubernetes API,
and verify the node-to-gateway and gateway-to-backend network paths. After
reconciliation, check that the DaemonSet is ready on every eligible node and the
cluster Collector has exactly one ready replica; inspect receiver/exporter error
and dropped-record metrics, confirm expected node/cluster metrics and workload
metadata, and check included/excluded test workloads. Observe resource use,
backend delivery, restart loss, queue saturation, and unchanged application
traces/database metrics before expanding use. No live Collector rollout or
end-to-end backend validation was performed for this change.

To roll back, revert or remove the two standalone entries from the development
root Kustomization and let Flux prune their Collector resources and RBAC. Do not
hand-delete Flux-owned resources. The existing gateway and database/cache
collector remain independently managed.

### Azure Key Vault (`terraform/keyvault`)

The VeloTimer message-bus topology Helm hook needs a separate Key Vault secret
named `velotime-messagebus-management` containing a Service Bus connection string
with Manage rights. Do not reuse the runtime `velotime-messagebus` credential.
The `velotime-secrets` ExternalSecret syncs it into the
`velotime-messagebus-management` Kubernetes Secret under the
`ConnectionStrings__MessageBusManagement` key, which the chart's topology Job
reads. Provision this credential in each environment's Key Vault before
installing or upgrading the chart.

The `module-profiles-api` deployment in the VeloTimer `v2` chart uses the existing
`velotimedb` database for its Profiles schema. Its ExternalSecret reads
`velotime-database-host`, `velotime-database-port`, `velotime-database-user`, and
`velotime-database-password`, plus `velotime-cache-host`, `velotime-cache-port`,
`velotime-cache-username`, and `velotime-cache-password`, already provisioned by
this module. It exposes the cache values as `CACHE_HOST`, `CACHE_PORT`,
`CACHE_USER`, and `CACHE_PASSWORD`, with TLS connections in `CACHE_URI` and
`ConnectionStrings__cache`. No additional vault credentials or Keycloak service
client are needed. The HelmRelease sets
`module-profiles-api.existingSecret` so both the API and its `profiles-migration`
init container receive the database connection. Application reconciliation
already waits for `velotime-secrets` and `velotime-db-grant`, and the init
container migrates the Profiles schema before the API starts.

The VeloTimer `v2` Notifications API and processor use External Secrets named
`module-notifications-api` and `module-notifications-processor`, selected by the
HelmRelease's `existingSecret` values. Both reuse the `velotime-database-*` and
`velotime-cache-*` vault credentials for `velotimedb` and TLS cache connections.
The processor and WebUI additionally read the runtime `velotime-messagebus`
credential as `ConnectionStrings__MessageBus`; provision it in the environment's
vault before reconciliation. No new vault secret names or Keycloak service client
are needed. Keep this runtime credential separate from
`velotime-messagebus-management`.

The chart creates the notification ConfigMaps using `global.oidcAuthority` and
`global.oidcAudience`, already set by the development overlay. Its WebUI ConfigMap
also supplies internal Notifications API service discovery; do not create
duplicate ConfigMaps or expose a separate API HTTPRoute. The chart's Notifications
migration hook uses the API's existing Secret, and application reconciliation
waits for `velotime-secrets` and `velotime-db-grant`. The development topology
already declares the non-session `webui-notifications` subscription with its
`NotificationsRefreshRequestedV1` filter. Since development disables the chart's
Valkey, the external cache must retain the Notifications Data Protection key ring
across restarts. Validate live Keycloak session claims, broker permissions, and
browser push delivery separately; manifest rendering does not verify them.

The core `terraform/` deployment provisions a per-environment Azure resource group (`velotime-infra-<basename>`) and Key Vault (`velotime-<basename>`), and writes the cache/database host, port, username, and Terraform-generated password into it as `velotime-cache-*`/`velotime-database-*` secrets. It also writes the database service port separately as `velotime-database-admin-port` for the database grant job. It creates a `keycloak` logical database with its own user, then writes those connection values as `keycloak-database-host`, `keycloak-database-port`, `keycloak-database-name`, `keycloak-database-user`, and `keycloak-database-password` — the same secret names the `external-secrets` `azure-keyvault` `ClusterSecretStore` reads from. Database usernames default to `velotime` for cache and application database access and `keycloak` for Keycloak database access. Database passwords are generated inside the Terraform modules and are not passed through GitHub environment secrets. Authentication uses `AZURE_TF_CLIENT_ID`/`AZURE_TENANT_ID`/`AZURE_SUBSCRIPTION_ID` via GitHub Actions OIDC (`ARM_USE_OIDC`); a matching federated credential must exist on that app registration in Azure AD for each environment (subject `repo:<org>/<repo>:environment:development`/`:environment:production`). The module grants itself `Key Vault Secrets Officer` and grants the existing `AZURE_ESO_OBJECT_ID` principal `Key Vault Secrets User`.

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

### Shared manifests and deployment layers

Reusable Flux definitions and resource bases are separated from cluster configuration:

| Layer | Shared configuration | Responsibility |
| --- | --- | --- |
| Infrastructure | [`infrastructure/`](infrastructure/) | Gateway API, Cilium, cert-manager/issuer, gateway, External Secrets/store, external-dns, OpenTelemetry operator, Keycloak namespace/operator |
| Services | [`services/`](services/) | Telemetry collector, Keycloak database grants/bootstrap credential, Keycloak instance/route |
| Applications | [`applications/`](applications/) | Velotime realm/client credentials, admin/social-login bootstrap and clients, all Velotime workloads |

Each shared layer's `kustomization.yaml` aggregates component
`flux-kustomization.yaml` definitions and upstream sources, not workload builds.
Local components have their own `kustomization.yaml`, manifests, and reusable
patches. Upstream components retain their upstream GitRepository paths.

The [development root](clusters/development/kustomization.yaml) includes its
FluxInstance, three layer Flux Kustomizations, and standalone database,
node-telemetry, and cluster-telemetry Kustomizations:

```text
infrastructure -> services -> applications
                       \----> database-opentelemetry-collector
                       \----> node-telemetry-collector
                       \----> cluster-telemetry-collector
```

Each layer builds its matching directory under
[`clusters/development/`](clusters/development/). That directory imports the shared
layer and patches component paths to development overlays where necessary.
Uncustomized components reconcile their shared base directly.
**Component `dependsOn` references stay within a layer.** Layer
Kustomizations establish the inter-layer dependencies; each standalone telemetry
Kustomization depends on the services layer and has no dependants of its own. The
old cross-boundary component dependencies are not retained.

Layer gates wait for all child Kustomizations to report Ready at their current
generation, with neither Reconciling nor Stalled set to True. Children wait for
their resources or use explicit health checks: the collector checks its generated
Deployment, Keycloak checks its Ready condition, and the gateway checks current
Accepted/Programmed conditions as well as certificate readiness. Layer timeouts
are 30 minutes, with one-minute retries.

These are Flux reconciliation gates, not runtime isolation or a global pause.
An upstream failure blocks the dependent **layer's** reconciliation; it does not
stop existing Pods or suspend already-created child Kustomizations, which continue
their own reconciliations. A fresh deployment creates downstream component
definitions only after the preceding layer is Ready.

Within services, `keycloak-db-grant` owns both the `keycloak-db-secret` and
`keycloak-db-admin-secret` ExternalSecrets alongside its database grant Job.
The Job starts once External Secrets has materialized its required Secret keys;
the component's `wait: true` gate requires the Job to complete before `keycloak`
reconciles. Keycloak also waits for `keycloak-bootstrap-secrets`. The database
secret must not be owned by `keycloak` itself, since that would prevent its
prerequisite grant Job from starting on a fresh installation.

The facilities API's `module-facilities-api` and statistics API's
`module-statistics-api` Secrets expose
`ConnectionStrings__MessageBus` from the existing `velotime-messagebus` secret in
the environment's Azure Key Vault, matching the timing API and processors.

Development overlays contain hostnames/URLs, Key Vault/tenant configuration, DNS
ownership/domain/resource-group settings, ACME contact, telemetry destination,
application revision/replica choices, and captured Cilium adoption values.
Keep `flux-kustomization.yaml` out of both its own component build and its own
layer build to avoid self-reconciliation. Import shared **directories**, so normal
Kustomize load restrictions remain enabled.

To opt another cluster in later, add its three layer definitions/aggregators and
root, then provide its component overlays and patch the corresponding Flux paths.
Do not copy development domains, vault/DNS settings, source revision, replica
settings, or captured Cilium values into that cluster. Several shared bases
deliberately omit required environment fields and are not directly deployable
until configured by an overlay. Production remains unchanged and is not opted in.
Keep bootstrap manifests at `clusters/<environment>/flux-system/flux-instance.yaml`.

Validate the root, each layer, and every effective local component path:

```sh
kubectl kustomize clusters/development
kubectl kustomize clusters/development/infrastructure
kubectl kustomize clusters/development/services
kubectl kustomize clusters/development/applications
# Examples of a development overlay and an uncustomized shared base:
kubectl kustomize clusters/development/infrastructure/cilium
kubectl kustomize applications/keycloak-clients
```

In a Python virtual environment outside the repository, install the layout-test
dependencies and run the offline regression tests:

```sh
python3 -m pip install -r tests/requirements.txt
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p '*_test.py' -v
```

The tests build all local bases/effective components, reject duplicate ownership
and cross-layer component dependencies, and evaluate gate CEL expressions against
missing, stale, progressing, failed, and Ready child statuses. They do not prove
live controller readiness, external connectivity, or a safe inventory handoff.

#### Existing development cluster: staged ownership handoff

**Do not deploy the final layout directly to an existing installation.** Moving
child Kustomizations out of the sync root changes their inventory owner; splitting
secret components also changes ownership of two ExternalSecrets. Pruning can
otherwise delete those objects and cascade into workloads, client finalizers, or
generated Secrets even though their rendered configuration is unchanged.

Use the [Flux resource-move procedure](https://fluxcd.io/flux/faq/#how-can-i-safely-move-resources-from-one-dir-to-another)
in separately reviewed intermediate Git revisions, against an explicitly selected
development context:

1. Before moving files, add
   `kustomize.toolkit.fluxcd.io/prune: disabled` annotations to **all 29 existing
   component Flux Kustomizations** and the two root-owned GitRepositories
   (`gateway-api` and `keycloak-operator-resources` in `flux-system`), plus the `external-dns-azure-config`
   ExternalSecret in `external-dns` and the `keycloak-bootstrap-admin`
   ExternalSecret in `keycloak`. Commit and reconcile the old layout. Verify the
   annotations are present on every affected live object without printing Secret
   contents.
2. Deploy an intermediate revision of the new layout that **retains those
   annotations at the destinations**. Do not remove protections in the same
   revision as the move. Keep object names/namespaces and pod templates unchanged.
   The annotations prevent old inventory pruning while new owners adopt them.
3. Reconcile and inspect the sync root and the three layer inventories, then the
   affected component inventories. Require the root to own only its FluxInstance
   and three layer definitions; each component must appear in exactly one layer.
   Require infrastructure to own both moved GitRepository sources,
   `external-dns-secrets` to own the DNS ExternalSecret, and
   `keycloak-bootstrap-secrets` to own the bootstrap ExternalSecret. Reconcile
   their old owners (`external-secrets-crs` and `keycloak-realm-secrets`) and verify
   those old inventories no longer contain the moved ExternalSecrets. Use
   `flux tree kustomization <name> -n flux-system` to inspect ownership.
4. Verify all layers/children are Ready, protected objects have no deletion
   timestamp, generated Secrets still exist, and no workload or bootstrap Job was
   replaced. Stop and investigate any pruning, adoption, or readiness failure;
   never delete a realm, client, database, or credential to force this move.
5. Only after the old inventories have released every moved object, remove the
   temporary annotations in a final revision (the steady-state layout in this
   repository). Reconcile and verify normal pruning and ownership again.

The handoff is an operational procedure, not performed by rendering tests or
automatically by this refactor. Verify live layer readiness, Keycloak realm/client
status and application authentication afterward; do not run user-data migrations
solely to validate the layout change.

#### Existing cluster: Keycloak database secret ownership handoff

If `keycloak` currently owns the `keycloak-db-secret` ExternalSecret, do not
deploy its move into `keycloak-db-grant` directly. Its `creationPolicy: Owner`
means pruning the ExternalSecret can also delete the generated database Secret.
Use separately reviewed intermediate Git revisions and an explicitly selected
cluster context, following the same resource-move procedure above:

1. In the old layout, add the annotation
   `kustomize.toolkit.fluxcd.io/prune: disabled` to the `keycloak-db-secret`
   ExternalSecret in `keycloak`. Reconcile its current `keycloak` owner and verify
   the live annotation before moving the manifest. If the owner cannot reconcile,
   stop and resolve the prerequisite failure rather than deploying an
   unprotected move.
2. Move the ExternalSecret into `keycloak-db-grant`, retaining that annotation at
   its destination. Keep the ExternalSecret's identity and spec, the generated
   Secret name, and the grant Job's pod template unchanged.
3. Reconcile `keycloak-db-grant`, then the old `keycloak` owner. Inspect both
   inventories using `flux tree kustomization <name> -n flux-system`: the grant
   component must own the ExternalSecret and the Keycloak inventory must no
   longer contain it. Verify the ExternalSecret is Ready, has no deletion
   timestamp, the generated Secret still exists, and the grant and Keycloak
   components are Ready. Do not print Secret contents.
4. Only after the old inventory has released the ExternalSecret, remove the
   temporary annotation in a final revision and reconcile again. Stop and
   investigate any pruning, adoption, or readiness failure; do not delete the
   Secret, database, or credentials to force the handoff.

Fresh installations can use the final layout directly. Offline layout tests
verify ownership and dependencies, not safe live inventory transfer or database
connectivity.

### Development WebUI Autoscaling

The [development Velotime overlay](clusters/development/applications/velotime/)
scales the WebUI between two and four replicas at 90% of its container memory
request (currently 256 MiB). The cluster must provide the Kubernetes resource
metrics API, such as through metrics-server. The HelmRelease post-renderer
removes the chart's fixed WebUI replica count so that the HPA can manage it;
other workloads retain their chart-defined replica counts. When changing the
chart, verify that the WebUI Deployment and container names and memory request
still match the autoscaler and that the post-render patch still applies.

Removing the existing Helm-managed replica field may temporarily reset the
Deployment to one replica during the first upgrade, before the HPA reconciles.
Check the HPA's metrics and conditions and the Deployment's replica count after
deployment; offline rendering does not verify the metrics API or live scaling.

### Development Keycloak Realm And Clients

The development realm is initialized by
[`keycloak-realm`](applications/keycloak-realm/keycloakrealmimport.yaml),
configured by its [development overlay](clusters/development/applications/keycloak-realm/).
It imports realm settings, roles, shared token scopes, a public-client PKCE policy,
and the public WebUI client, but no users. The baseline is the application's
[`velotime-realm.json`](https://github.com/asbjorjo/VeloTimer/blob/8e5b046df98666355d2351e157e794854b79135b/config/keycloak/realms/velotime-realm.json),
without its test account or wildcard redirects. Built-in scopes are explicitly
preserved alongside `velotime:all`; the shared scope supplies the exact API audience
`https://development.veloti.me`, subject, realm roles and client-role claims even
when a service requests a token without specifying scopes.

[`keycloak-clients`](applications/keycloak-clients/kustomization.yaml)
manages the three service clients separately using the operator's
`KeycloakOIDCClient` v2alpha1 API.
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
Google and Facebook identity providers are reconciled separately as described
below. SMTP is not provisioned here.

The WebUI client is initialized by the realm import, not continuously reconciled
as a `KeycloakOIDCClient`. Realm imports skip existing realms, so changing this
definition does not update an already deployed realm. Before deploying this move
to an existing environment, arrange an explicit ownership handoff for the existing
`velotime.webui` client: verify its settings in Keycloak and the operator's deletion
behavior before allowing Flux to prune the old CR. Do not delete the realm to
re-run the import.

#### Google And Facebook Login

The `keycloak-admin-bootstrap` component includes a `keycloak-social-logins`
CronJob that reconciles the `google` and `facebook` aliases every five minutes.
It works for both new and existing `velotime` realms without deleting or
reimporting the realm. Both providers appear on the login screen, request email
access, use the built-in `first broker login` flow, and do not automatically
trust provider email addresses or store provider tokens. Existing-account linking
retains Keycloak's default verification requirements.

Before deploying, create real OAuth applications in Google Cloud and Meta's
developer console and populate these four secrets in the development Azure Key
Vault (these are externally issued credentials, not Terraform-generated values):

| Provider | Client ID / app ID vault secret | Client / app secret vault secret | Authorized redirect URI |
| --- | --- | --- | --- |
| Google | `keycloak-google-client-id` | `keycloak-google-client-secret` | `https://auth.development.veloti.me/realms/velotime/broker/google/endpoint` |
| Facebook | `keycloak-facebook-client-id` | `keycloak-facebook-client-secret` | `https://auth.development.veloti.me/realms/velotime/broker/facebook/endpoint` |

Configure the Google consent screen/audience and Meta app domains, Facebook Login
and app mode/review requirements for the users who should sign in. Development
or testing apps may restrict login to explicitly listed testers.

External Secrets copies these values into `keycloak-social-logins` in the
`keycloak` namespace. Missing vault values prevent that ExternalSecret from
becoming Ready and block the bootstrap Kustomization and its dependents; provision
them before rollout. Rotation is picked up on the next scheduled run after the
one-hour ExternalSecret refresh. Each run writes the vault secret even when
Keycloak masks the stored value. Only these two aliases are managed; other
providers and additional provider configuration are preserved. Removing the
CronJob does not delete the providers. Do not edit managed fields in the Admin UI;
the next run restores them.

**Existing installations require a one-time permission grant before rollout:**
using an independently authorized master-realm administrator, select the
`velotime-operator` client in `master`, then its service-account role mappings.
Grant the **master realm's `velotime-realm` client's**
`manage-identity-providers` role. This is scoped to the `velotime` realm; do not
grant `realm-admin` or master administration. The operator cannot grant itself this
role after temporary bootstrap access has been removed. New installations receive
the role automatically. The changed scripts replace the bootstrap Job; its
permission verification must pass, so grant the role before deploying this change.

The first scheduled run occurs within five minutes after deployment. Check the
ExternalSecret is Ready and the CronJob's latest Job succeeds; CronJob creation
alone does not confirm that provider reconciliation succeeded. Failures are
reported in Job status and sanitized logs, including HTTP status for API errors.
Then test both login buttons with authorized test accounts, including existing
account linking. No live OAuth credentials or login tests are run by repository
unit tests.

#### First Deployment Prerequisites

The core `terraform/` deployment automatically generates all three application
client secrets above and these two additional, independent credentials in each
environment's Azure Key Vault before Flux bootstrap runs:

- `keycloak-bootstrap-admin-client-secret`: temporary master-realm bootstrap service account.
- `keycloak-operator-client-secret`: permanent operator service account.

Each credential is a separate 32-character alphanumeric `random_password`, retained
in OpenTofu state across applies. No manual secret generation or Keycloak Admin UI
interaction is needed for a fresh installation once GitHub/Azure authentication
and External Secrets access are configured. These credentials are sensitive state
data; restrict access to the state bucket and never expose their values in logs.

The vault resources seed values only on creation (`ignore_changes = [value]`), so
later applies do not undo coordinated credential rotation. Replacing a random
resource alone does not rotate an existing vault secret or Keycloak account.

**Existing installations:** before applying this change, import each of the five
existing vault secrets into the core deployment's matching resource address,
`module.keyvault.azurerm_key_vault_secret.keycloak_client["<secret-name>"]`, using
its Azure Key Vault secret identifier. Use the explicitly selected environment's
backend and variable file, following the backend setup above. Imported values are
preserved even though the new random resources generate unused initial values.
Review the environment's plan to ensure no existing credential is replaced; do
not delete/recreate secrets to resolve ownership conflicts. Importing secrets does
not provision missing admin accounts in an already-initialized Keycloak database.

In the services layer, `keycloak-bootstrap-secrets` mirrors the temporary bootstrap
credential into the `keycloak` namespace before Keycloak starts. In the applications
layer, `keycloak-realm-secrets` mirrors the permanent operator and application
client credentials into that namespace.
The bootstrap and permanent Kubernetes Secrets are `keycloak-bootstrap-admin`
and `keycloak-admin`, with fixed client IDs `velotime-bootstrap-admin` and
`velotime-operator` respectively. The operator reads `client-id`/`client-secret`
from `keycloak-admin`. Application workloads keep their existing secrets in
the `velotime` namespace; no secret values are committed to Git.

**This automatic bootstrap requires a new Keycloak database without a master realm.**
`spec.bootstrapAdmin.service` is ignored once the master realm exists. Do not delete
or reset an existing database to satisfy this requirement; use a separately reviewed
admin recovery/provisioning procedure for an already-initialized installation.

Flux first makes infrastructure Ready, then applies service-owned bootstrap
credentials and database grants before Keycloak. Once services are Ready, the
applications layer applies the realm import and realm/client secrets, then
`keycloak-admin-bootstrap`, then `keycloak-clients`. Application deployment and
migration wait for successful client reconciliation. The bootstrap Job uses the
temporary account to create the permanent account in `master`, granting only the
Velotime management client's `manage-clients`, `view-clients`, `manage-users`,
`view-users`, `manage-realm`, and `manage-identity-providers` roles. It grants no
master-realm administration or permission to create other realms. It verifies permanent API access before
deleting the temporary account. A retry works after cleanup using permanent
credentials; failed verification retains temporary access. Retained completed
Jobs are not periodically rerun. A changed bootstrap script replaces its Job via
the Flux force annotation; it must remain idempotent.

The operator account is not a human master administrator. Establish an independent,
secure recovery procedure before removing bootstrap access. If master administration
is later needed, follow Keycloak's
[admin recovery guide](https://www.keycloak.org/server/bootstrap-admin-recovery);
the recovery command requires all Keycloak nodes to be stopped.

The bootstrap Job uses separate Pods for retries (`restartPolicy: Never`) so
failed attempts retain their logs until the Job is replaced or deleted. Python
output is unbuffered; progress logs identify each access check and report HTTP
status without credentials or response bodies. Inspect failures with
`kubectl -n keycloak get pods -l job-name=keycloak-admin-bootstrap` and
`kubectl -n keycloak logs <pod-name>`. A failed Job is terminal; Flux's force
annotation replaces it when its pod template changes, not on every reconciliation.
If realm endpoints return 404 while the import CR still reports `Done=True`,
verify realm discovery directly: the import completion flag does not detect a
realm deleted after import. Restore or recreate that realm only through a
separately reviewed recovery procedure; restarting bootstrap does not restore
realm data.

#### Reconciliation And Verification

`KeycloakRealmImport` creates a realm only once: edits do not update an existing
realm or delete it. Keep the import CR managed by Flux to retain its completion
status and avoid recreating a tracked resource through manual cleanup. Changes to
realm settings (other than the separately reconciled social providers), policies,
scopes or composite roles after import need a separately reviewed update procedure,
not a realm deletion/reimport.

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

Run the vault credential tests with mocked Azure resources (no cloud access),
after `tofu -chdir=terraform init -backend=false -input=false`:

```sh
tofu -chdir=terraform test -filter=tests/keycloak_bootstrap.tftest.hcl
```

Run the bootstrap and social login safety tests with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s applications/keycloak-admin-bootstrap -p '*_test.py' -v
```

Build the four new components separately as well as the development root. After
deployment to the explicitly selected development context, verify ExternalSecrets
are Ready, the realm import reports `Done=True`, the bootstrap Job is Complete,
and every client reports current `observedGeneration`, a nonempty `hash`, and
`HasErrors=False`. The Flux health expressions reject missing or stale client status.
Client readiness does not require `status.uuid`, which the operator may omit even
after successful reconciliation.
Check realm discovery at
`https://auth.development.veloti.me/realms/velotime/.well-known/openid-configuration`,
then test WebUI login/logout and fresh service tokens' exact issuer, audience,
subject and permitted/forbidden API operations. Never print secrets or tokens in
logs, and do not run user-data migrations solely as an authentication test.
