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

Providers authenticate against the cluster module's UpCloud-managed cluster; UpCloud has no bearer token, only client cert/key.
provider "helm" {
  kubernetes = {
    host                   = module.cluster.host
    cluster_ca_certificate = module.cluster.cluster_ca_certificate
    client_certificate     = module.cluster.client_certificate
    client_key             = module.cluster.client_key
  }
}

provider "kubernetes" {
  host                   = module.cluster.host
  cluster_ca_certificate = module.cluster.cluster_ca_certificate
  client_certificate     = module.cluster.client_certificate
  client_key             = module.cluster.client_key
}