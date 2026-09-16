# Agent Guidance

## Repository Shape

- This is an OpenTofu/Terraform infrastructure repository for UpCloud.
- The `terraform/` root module composes `network`, `cluster`, `cache`, and `database`; Flux bootstrap runs after the cluster is available. Flux manifests remain under `clusters/`.
- Keep module inputs and outputs explicit. Preserve the dependency flow through root-module references and `depends_on` where provider initialization requires it.
- Root Helm and Kubernetes providers authenticate with the cluster client certificate, key, and CA exported by `cluster`; do not replace this with a bearer-token assumption.

## Development Workflow

- Format and validate with `tofu -chdir=terraform fmt -check`, `tofu -chdir=terraform init -backend=false -input=false`, and `tofu -chdir=terraform validate -no-color`.
- Use the same OpenTofu version as CI (`1.12.5`) when reproducing workflow behavior.
- Environment-backed plan/apply requires S3-compatible backend configuration for UpCloud Object Storage. Do not run a state-backed command until the intended environment and backend are explicit.
- Review `.github/workflows/terraform-plan.yml` and `.github/workflows/terraform-apply.yml` before changing CI or deployment behavior.

## Safety and Secrets

- Never commit state, `.env` files, kubeconfigs, credentials, or generated `.terraform` contents; see `.gitignore`.
- Treat `TF_VAR_*`, provider credentials, SSH keys, IP filters, database credentials, and `FLUX_GIT_TOKEN` as sensitive. Do not print or hard-code them.
- Keep `store_kubeconfig = false` for automated/root-module usage unless a local kubeconfig file is explicitly required and handled securely.
- Do not change the backend state key or migrate state without an explicit, reviewed operational plan.

## Environment and Flux

- `var.environment` selects `clusters/<environment>/flux-system/flux-instance.yaml` from the `terraform/` root module; a matching manifest must exist before applying that environment.
- Changes to infrastructure plans, networking, access filters, credentials, or Flux bootstrap have deployment impact and should be reviewed with a plan for the target environment.
- Resource names derive from `var.basename`; preserve that convention when adding resources.

See [README.md](README.md) for GitHub environment variables, secrets, backend setup, and Flux bootstrap details.