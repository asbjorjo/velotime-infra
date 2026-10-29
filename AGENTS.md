# Agent Guidance

## Repository Shape

- This is an OpenTofu/Terraform infrastructure repository for UpCloud.
- The `terraform/` root module composes `network`, `cluster`, `cache`, and `database`. Flux bootstrap is a separate deployment in `flux-bootstrap/`, applied after `terraform/` via its own state and workflow. Reusable Flux bases live in `infrastructure/`, `services/`, and `applications/`; cluster roots, layer gates, environment overlays, and FluxInstance manifests live under `clusters/`.
- Development uses the layer chain `infrastructure` -> `services` -> `applications`. Component `dependsOn` references must remain within their layer; only layer gates depend on other layers. Keep each component/layer's Flux definition out of its own Kustomize build.
- Keep module inputs and outputs explicit. Preserve the dependency flow through root-module references and `depends_on` where provider initialization requires it.
- `flux-bootstrap/`'s Helm and Kubernetes providers read a kubeconfig file fetched by CI via `upctl kubernetes config <basename>-cluster`, not Terraform-managed cluster outputs; `terraform/` has no `helm`/`kubernetes` provider.

## Development Workflow

- Format and validate with `tofu -chdir=terraform fmt -check`, `tofu -chdir=terraform init -backend=false -input=false`, and `tofu -chdir=terraform validate -no-color`. Repeat with `-chdir=flux-bootstrap` for the Flux bootstrap deployment.
- Use the same OpenTofu version as CI (`1.12.5`) when reproducing workflow behavior.
- If OpenTofu `1.12.5`, `kubectl`, or the Python test virtual environment with `tests/requirements.txt` installed is unavailable, do not attempt a global install; state clearly which validation steps were skipped and why, and ask before installing tooling.
- Environment-backed plan/apply requires S3-compatible backend configuration for UpCloud Object Storage. Do not run a state-backed command until the intended environment and backend are explicit.
- Review `.github/workflows/terraform-plan.yml`, `.github/workflows/terraform-apply.yml`, and `.github/workflows/flux-bootstrap-apply.yml` before changing CI or deployment behavior.
- For Flux changes, build the cluster root, layer aggregators, and effective component paths with `kubectl kustomize`. With `tests/requirements.txt` installed in an external Python virtual environment, run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p '*_test.py' -v`. Keycloak safety tests live in `applications/keycloak-admin-bootstrap`.

## Git Workflow

- Before starting new work, fetch the remote that tracks `main`, switch to `main`, and update it with a fast-forward-only pull from its configured upstream. Create a descriptive topic branch from that synced `main`; do not commit directly to `main`.
- If `main` has no configured upstream, the fetch/pull fails, local `main` has diverged, or switching would disturb existing work, stop and ask for guidance. Do not reset, discard, or automatically stash user changes.
- Keep commits atomic: each commit should contain one logical change and its directly related tests or documentation. Review the staged diff and stage only task-related files or hunks; leave unrelated changes untouched.
- Use Conventional Commit messages in the form `type(scope): description`, with an optional scope (for example, `docs: clarify agent Git workflow` or `fix(cluster): correct node configuration`).

## Safety and Secrets

- Never commit state, `.env` files, kubeconfigs, credentials, or generated `.terraform` contents; see `.gitignore`.
- Treat `TF_VAR_*`, provider credentials, SSH keys, IP filters, database credentials, and `FLUX_GIT_TOKEN` as sensitive. Do not print or hard-code them.
- Keep `store_kubeconfig = false` in `terraform/`. Only set it to `true` if the user explicitly requests it, the output path is covered by `.gitignore`, and the change is confined to a local-only (non-CI) configuration.
- Do not change the backend state key or migrate state without an explicit, reviewed operational plan.

## Environment and Flux

- `var.environment` selects `clusters/<environment>/flux-system/flux-instance.yaml` from the `flux-bootstrap/` root module; a matching manifest must exist before applying that environment.
- Changes to infrastructure plans, networking, access filters, credentials, or Flux bootstrap have deployment impact and should be reviewed with a plan for the target environment.
- Moving resources between Flux inventories requires the staged pruning-protection and ownership-handoff procedure in README; identical rendered resources alone do not make a move safe.
- Resource names derive from `var.basename`; preserve that convention when adding resources. `flux-bootstrap/` assumes the cluster is named `<basename>-cluster` and does not take `basename` as a Terraform variable itself — CI resolves the cluster name via `upctl`.

See [README.md](README.md) for GitHub environment variables, secrets, backend setup, and Flux bootstrap details.