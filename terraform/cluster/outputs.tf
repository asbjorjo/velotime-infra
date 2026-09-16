output "cluster_id" {
  value = upcloud_kubernetes_cluster.instance.id
}

output "host" {
  value = data.upcloud_kubernetes_cluster.instance.host
}

output "cluster_ca_certificate" {
  value     = data.upcloud_kubernetes_cluster.instance.cluster_ca_certificate
  sensitive = true
}

output "client_certificate" {
  value     = data.upcloud_kubernetes_cluster.instance.client_certificate
  sensitive = true
}

output "client_key" {
  value     = data.upcloud_kubernetes_cluster.instance.client_key
  sensitive = true
}
