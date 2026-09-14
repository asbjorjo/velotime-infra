# Velotime Infrastructure

## GitHub Actions

Configure these repository secrets before running the OpenTofu workflows:

- `UPCLOUD_TOKEN`: UpCloud API token used by the provider.
- `UPCLOUD_S3_ACCESS_KEY_ID`: UpCloud Object Storage access key ID.
- `UPCLOUD_S3_SECRET_ACCESS_KEY`: UpCloud Object Storage secret access key.

The Object Storage credentials should have read and write access only to the `velotime-tfstate-dev` bucket and the `velotime-infra/terraform.tfstate` state key. Migrate the existing local state to Object Storage before the apply workflow runs.

Pull requests from forks run formatting and backend-free validation only; state-backed plans run for trusted pull requests and manual workflow dispatches.
