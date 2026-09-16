# Agent Guidance

## Repository Shape

- This is an OpenTofu/Terraform infrastructure repository for UpCloud.
- The `terraform/` root module composes `network`, `cluster`, `cache`, and `database`. Flux bootstrap is a separate deployment in `flux-bootstrap/`, applied after `terraform/` via its own state and workflow. Flux manifests remain under `clusters/`.
- Keep module inputs and outputs explicit. Preserve the dependency flow through root-module references and `depends_on` where provider initialization requires it.
- `flux-bootstrap/`'s Helm and Kubernetes providers read a kubeconfig file fetched by CI via `upctl kubernetes config <basename>-cluster`, not Terraform-managed cluster outputs; `terraform/` has no `helm`/`kubernetes` provider.

## Development Workflow

- Format and validate with `tofu -chdir=terraform fmt -check`, `tofu -chdir=terraform init -backend=false -input=false`, and `tofu -chdir=terraform validate -no-color`. Repeat with `-chdir=flux-bootstrap` for the Flux bootstrap deployment.
- Use the same OpenTofu version as CI (`1.12.5`) when reproducing workflow behavior.
- Environment-backed plan/apply requires S3-compatible backend configuration for UpCloud Object Storage. Do not run a state-backed command until the intended environment and backend are explicit.
- Review `.github/workflows/terraform-plan.yml`, `.github/workflows/terraform-apply.yml`, and `.github/workflows/flux-bootstrap-apply.yml` before changing CI or deployment behavior.

## Safety and Secrets

- Never commit state, `.env` files, kubeconfigs, credentials, or generated `.terraform` contents; see `.gitignore`.
- Treat `TF_VAR_*`, provider credentials, SSH keys, IP filters, database credentials, and `FLUX_GIT_TOKEN` as sensitive. Do not print or hard-code them.
- Keep `store_kubeconfig = false` for automated/root-module usage unless a local kubeconfig file is explicitly required and handled securely.
- Do not change the backend state key or migrate state without an explicit, reviewed operational plan.

## Environment and Flux

- `var.environment` selects `clusters/<environment>/flux-system/flux-instance.yaml` from the `flux-bootstrap/` root module; a matching manifest must exist before applying that environment.
- Changes to infrastructure plans, networking, access filters, credentials, or Flux bootstrap have deployment impact and should be reviewed with a plan for the target environment.
- Resource names derive from `var.basename`; preserve that convention when adding resources. `flux-bootstrap/` assumes the cluster is named `<basename>-cluster` and does not take `basename` as a Terraform variable itself — CI resolves the cluster name via `upctl`.

See [README.md](README.md) for GitHub environment variables, secrets, backend setup, and Flux bootstrap details.