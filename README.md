# Velotime Infrastructure

## GitHub Actions

Workflows use GitHub [deployment environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment):

- Pull requests to `main` or `production` run `tofu -chdir=terraform fmt -check` and `tofu -chdir=flux-bootstrap fmt -check` only.
- Pushes to `main` run the core `terraform/` deployment (development plan and apply, then production plan, then production apply after manual approval). After each environment's core apply succeeds, that environment's `flux-bootstrap/` deployment runs plan and apply automatically.

The core `terraform/` deployment uses the `production-approval` gate. Configure required reviewers on `production-approval` so production apply pauses after a successful production plan. The `flux-bootstrap/` deployment does not require a separate production approval; it runs after the already-approved production core apply succeeds. Keep Terraform variables and secrets on the `development` and `production` environments; if production plan should run automatically, do not put required reviewers on the `production` environment itself.

Each deployment job's GitHub Environment is used directly as the Terraform basename and state bucket name:

- `development`: Terraform basename and state bucket `development`.
- `production`: Terraform basename and state bucket `production`.

### Environment Configuration

Configure the following variables in each Terraform GitHub Environment (`development` and `production`):

- `BACKEND_REGION`: The region of the Object Storage bucket (e.g., `europe-1`).
- `BACKEND_ENDPOINT`: The S3-compatible endpoint URL (e.g., `https://spfj4.upcloudobjects.com`).
- `ADMIN_IP_FILTER`: JSON array of allowed IP addresses/CIDRs for admin access, such as `["203.0.113.10/32"]`. Passed as-is to Terraform's `admin_ip_filter` variable, which sets the cluster's `control_plane_ip_filter`. The `flux-bootstrap` workflow separately opens the control-plane API to its own runner's IP for the duration of its run (see [Flux CD Bootstrap](#flux-cd-bootstrap)); it does not modify this variable's persisted value.
- `ZONE` **(required)**: UpCloud zone used by the `network`, `cluster`, `cache`, and `database` modules (e.g., `fi-hel1`).
- `NETWORK_GATEWAY_PLAN` *(optional)*: UpCloud plan for the NAT gateway. Defaults to `essentials`.
- `NETWORK_IP_RANGE` *(optional)*: CIDR range for the cluster SDN network. Defaults to `172.16.2.0/24`.
- `CLUSTER_PLAN` *(optional)*: UpCloud plan for the Kubernetes cluster control plane. Defaults to `dev-md`.
- `CLUSTER_NODE_PLAN` *(optional)*: UpCloud plan for the Kubernetes worker nodes. Defaults to `CLOUDNATIVE-1xCPU-4GB`.
- `CACHE_PLAN` *(optional)*: UpCloud plan for the cache instance. Defaults to `1x1xCPU-1GB`.
- `DATABASE_PLAN` *(optional)*: UpCloud plan for the database instance. Defaults to `1x1xCPU-1GB-10GB`.

### Secrets

Configure these secrets (at the environment or repository level):

- `UPCLOUD_TOKEN`: UpCloud API token used by the provider.
- `UPCLOUD_S3_ACCESS_KEY_ID`: UpCloud Object Storage access key ID.
- `UPCLOUD_S3_SECRET_ACCESS_KEY`: UpCloud Object Storage secret access key.
- `CLUSTER_SSH_KEYS`: SSH public keys for cluster access.
- `DATABASE_USERNAME` / `DATABASE_PASSWORD`: Database credentials.
- `CACHE_DB_USERNAME` / `CACHE_DB_PASSWORD`: Cache database credentials.

The `flux-bootstrap` workflow additionally requires:

- `FLUX_GIT_TOKEN`: GitHub PAT with read access to this repo, used as the Flux `flux-system` git pull secret.
- `UPCLOUD_TOKEN`, `UPCLOUD_S3_ACCESS_KEY_ID`, `UPCLOUD_S3_SECRET_ACCESS_KEY` (shared with the core deployment above).

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
`clusters/<environment>/flux-system/flux-instance.yaml`, where `<environment>` is the
GitHub Actions deployment environment (`development` or `production`) passed in
automatically as `TF_VAR_environment` — a matching manifest must exist for each environment
before that environment's plan or apply can succeed. The `flux-system` git pull secret used by
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
