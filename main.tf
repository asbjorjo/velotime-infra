terraform {
 required_version = ">= 1.7.0" # OpenTofu 1.7+ for encryption
 required_providers {
   upcloud = {
     source  = "upcloudltd/upcloud"
     version = "~> 5.0"
   }
 }
}

provider "upcloud" {
}

module "cluster" {
  source = "./cluster"

  basename         = var.basename
  store_kubeconfig = true
  zone             = var.zone
}