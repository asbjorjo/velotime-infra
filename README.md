# Velotime Infrastructure

## GitHub Actions

Workflows use GitHub [deployment environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment):
- `development`: Runs on pushes to the `main` branch or PRs targeting `main`.
- `production`: Runs on pushes to the `production` branch or PRs targeting `production`.

Manual runs via `workflow_dispatch` allow selecting either the `development` or `production` environment.

The selected GitHub Environment is used directly as the Terraform basename and state bucket name:

- `development`: Terraform basename and state bucket `development`.
- `production`: Terraform basename and state bucket `production`.

### Environment Configuration

Configure the following variables in each GitHub Environment (`development` and `production`):

- `BACKEND_REGION`: The region of the Object Storage bucket (e.g., `europe-1`).
- `BACKEND_ENDPOINT`: The S3-compatible endpoint URL (e.g., `https://spfj4.upcloudobjects.com`).
- `ADMIN_IP_FILTER`: Allowed IP addresses/CIDRs JSON/string list for admin access.
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

The derived Object Storage buckets must exist before their workflows run. Object Storage credentials should have read and write access to the respective state bucket and the `velotime-infra/terraform.tfstate` state key. Migrate existing state, including state in legacy buckets such as `velotime-tfstate-dev`, to the derived bucket before the apply workflow runs.

Pull requests from forks run formatting and backend-free validation only; state-backed plans run for trusted pull requests and manual workflow dispatches.
