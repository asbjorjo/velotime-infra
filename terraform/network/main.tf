# Create a router for your network
resource "upcloud_router" "instance" {
  name = "${var.basename}-router"
}

# Create a network for your cluster
resource "upcloud_network" "instance" {
  name = "${var.basename}-net"
  zone = var.zone

  ip_network {
    address            = var.ip_network_range
    dhcp               = true
    dhcp_default_route = true
    family             = "IPv4"
  }

  router = upcloud_router.instance.id
}

# Create a Managed NAT GW for Internet connectivity from the SDN network
resource "upcloud_gateway" "instance" {
  name     = "${var.basename}-gw"
  zone     = var.zone
  features = ["nat"]
  plan     = var.gateway_plan

  router {
    id = upcloud_router.instance.id
  }
}