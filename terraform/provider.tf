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
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}

  use_oidc = true
}