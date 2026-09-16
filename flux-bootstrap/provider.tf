terraform {
  backend "s3" {
    key                         = "velotime-infra/flux-bootstrap.tfstate"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_requesting_account_id  = true
  }

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = ">= 3.0.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 3.0.0"
    }
  }
}

# Kubeconfig is fetched by CI via `upctl kubernetes config` before OpenTofu runs; not managed by Terraform.
provider "helm" {
  kubernetes = {
    config_path = "${path.module}/kubeconfig.yml"
  }
}

provider "kubernetes" {
  config_path = "${path.module}/kubeconfig.yml"
}
