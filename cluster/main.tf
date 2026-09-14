# Create a cluster
resource "upcloud_kubernetes_cluster" "instance" {
  name                    = "${var.basename}-cluster"
  network                 = var.network
  zone                    = var.zone
  private_node_groups     = true
  depends_on              = [var.gateway]
  control_plane_ip_filter = var.admin_ip_filter
  plan                    = var.plan
}

# Create a node group for your cluster
# Node group is a group of worker nodes that are created based on the same template
# You can have multiple node groups with different configurations in your cluster
resource "upcloud_kubernetes_node_group" "group" {
  name = "default"

  // All nodes in this group will be joined to this cluster
  cluster = upcloud_kubernetes_cluster.instance.id

  // The amount of created nodes (servers)
  node_count = var.nodes

  // Plan for each node; you can check available plans with upcloud CLI tool (`upctl server plans`) or by making a call to API (https://developers.upcloud.com/1.3/7-plans/)
  plan = var.node_plan

  cloud_native_plan {
    storage_tier = "standard"
    storage_size = 20
  }

  // With `anti_affinity` set to true, UKS will attempt to deploy nodes in this group to different compute hosts
  anti_affinity = true

  // Each node in this group will have the following labels
  labels = {
    managedBy = "terraform"
    project   = "velotime-dev"
  }

  // If uncommented, Eeach node in this group will have this taint
  # taint {
  #   effect = "NoExecute"
  #   key    = "key"
  #   value  = "value"
  # }

  // Each node in this group will have keys defined in this list configured as authorized keys (for "debian" user)
  ssh_keys = var.ssh_keys
}

data "upcloud_kubernetes_cluster" "instance" {
  id = upcloud_kubernetes_cluster.instance.id
}

# With `hashicorp/local` Terraform provider one can output the kubeconfig to a file. The file can be easily
# used to configure `kubectl` or any other Kubernetes client.
resource "local_file" "kubeconfig" {
  count = var.store_kubeconfig ? 1 : 0

  content  = data.upcloud_kubernetes_cluster.instance.kubeconfig
  filename = "${path.module}/kubeconfig.yml"
}
