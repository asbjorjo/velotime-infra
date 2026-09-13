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
