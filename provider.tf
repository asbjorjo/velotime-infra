terraform {
  backend "s3" {
    key                         = "velotime-infra/terraform.tfstate"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_requesting_account_id  = true
  }

  required_providers {
    upcloud = {
      source  = "UpCloudLtd/upcloud"
      version = ">= 5.34.0"
    }
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

# Providers authenticate with the kubeconfig written by the cluster module.
provider "helm" {
  kubernetes = {
    config_path = module.cluster.kubeconfig_path
  }
}

provider "kubernetes" {
  config_path = module.cluster.kubeconfig_path
}