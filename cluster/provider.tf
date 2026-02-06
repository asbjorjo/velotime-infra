terraform {
  required_providers {
    upcloud = {
      source  = "upcloudLtd/upcloud"
      version = ">= 2.11.0"
    }
  }
}

# provider "upcloud" {
# }

# Kubernetes provider configuration uses the data source
provider "kubernetes" {
  client_certificate     = data.upcloud_kubernetes_cluster.example.client_certificate
  client_key             = data.upcloud_kubernetes_cluster.example.client_key
  cluster_ca_certificate = data.upcloud_kubernetes_cluster.example.cluster_ca_certificate
  host                   = data.upcloud_kubernetes_cluster.example.host
}