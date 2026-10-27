mock_provider "upcloud" {}
mock_provider "random" {}

variables {
  zone    = "fi-hel1"
  network = "00000000-0000-0000-0000-000000000001"
}

run "default_database_plan" {
  command = plan

  module {
    source = "./database"
  }

  assert {
    condition = (
      upcloud_managed_database_postgresql.instance.plan_compute == "rdb.development.1CPU-1GB" &&
      upcloud_managed_database_postgresql.instance.plan_node_count == 1 &&
      upcloud_managed_database_postgresql.instance.plan_storage_gib == 10 &&
      upcloud_managed_database_postgresql.instance.plan_backups == "mini"
    )
    error_message = "The database must default to the requested single-node development plan with 10 GiB and mini backups."
  }
}

run "custom_database_plan" {
  command = plan

  module {
    source = "./database"
  }

  variables {
    plan_compute     = "rdb.standard.2CPU-8GB"
    plan_node_count  = 2
    plan_storage_gib = 120
    plan_backups     = "regular"
  }

  assert {
    condition = (
      upcloud_managed_database_postgresql.instance.plan_compute == var.plan_compute &&
      upcloud_managed_database_postgresql.instance.plan_node_count == var.plan_node_count &&
      upcloud_managed_database_postgresql.instance.plan_storage_gib == var.plan_storage_gib &&
      upcloud_managed_database_postgresql.instance.plan_backups == var.plan_backups
    )
    error_message = "The database must forward all componentized plan inputs to the provider."
  }
}
