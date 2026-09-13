# Velotime Infrastructure

## State Backend

Terraform/OpenTofu state is stored in UpCloud Object Storage through its S3-compatible API. The bucket must already exist before initializing the backend.

1. Create the local backend configuration:

   ```sh
   cp backend.s3.tfbackend.example backend.s3.tfbackend
   ```

2. Export an UpCloud Object Storage access key with read and write access to `velotime-tfstate-dev`:

   ```sh
   export AWS_ACCESS_KEY_ID="..."
   export AWS_SECRET_ACCESS_KEY="..."
   ```

3. Initialize and migrate the existing local state when prompted:

   ```sh
   tofu init -backend-config=backend.s3.tfbackend
   ```

After initialization, verify backend access and configuration with:

```sh
tofu validate
tofu state list
```

The local `backend.s3.tfbackend` is intentionally ignored. Do not commit Object Storage credentials.

## GitHub Actions

Configure these repository secrets before running the OpenTofu workflows:

- `UPCLOUD_TOKEN`: UpCloud API token used by the provider.
- `UPCLOUD_S3_ACCESS_KEY_ID`: UpCloud Object Storage access key ID.
- `UPCLOUD_S3_SECRET_ACCESS_KEY`: UpCloud Object Storage secret access key.

The Object Storage credentials should have read and write access only to the `velotime-tfstate-dev` bucket and the `velotime-infra/terraform.tfstate` state key. Migrate the existing local state to Object Storage before the apply workflow runs.

Pull requests from forks run formatting and backend-free validation only; state-backed plans run for trusted pull requests and manual workflow dispatches.
