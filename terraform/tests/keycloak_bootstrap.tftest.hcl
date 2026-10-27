mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id = "00000000-0000-0000-0000-000000000001"
      object_id = "00000000-0000-0000-0000-000000000002"
    }
  }

  mock_resource "azurerm_key_vault" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000003/resourceGroups/velotime-infra-test/providers/Microsoft.KeyVault/vaults/velotime-test"
    }
  }
}

mock_provider "time" {}

variables {
  basename                         = "test"
  location                         = "westeurope"
  eso_principal_object_id          = "00000000-0000-0000-0000-000000000004"
  cache_host                       = "cache.example.invalid"
  cache_port                       = "6379"
  cache_username                   = "test"
  cache_password                   = "test-only-cache-password"
  database_host                    = "database.example.invalid"
  database_port                    = "5432"
  database_admin_database          = "defaultdb"
  database_admin_username          = "admin"
  database_admin_password          = "test-only-database-admin-password"
  database_username                = "velotime"
  database_password                = "test-only-database-password"
  keycloak_database_host           = "database.example.invalid"
  keycloak_database_port           = "5432"
  keycloak_database_name           = "keycloak"
  keycloak_database_username       = "keycloak"
  keycloak_database_password       = "test-only-keycloak-password"
  keycloak_database_admin_database = "defaultdb"
  keycloak_database_admin_username = "admin"
  keycloak_database_admin_password = "test-only-database-admin-password"
}

run "seed_keycloak_secrets" {
  command = apply

  module {
    source = "./keyvault"
  }

  assert {
    condition = toset([for secret in azurerm_key_vault_secret.keycloak_client : secret.name]) == toset([
      "keycloak-bootstrap-admin-client-secret",
      "keycloak-operator-client-secret",
      "velotime-migration-users-secret",
      "velotime-statistics-secret",
      "velotime-timing-secret",
    ])
    error_message = "The vault must contain exactly the five credentials consumed by External Secrets."
  }

  assert {
    condition = alltrue([
      for name, password in random_password.keycloak_client :
      can(regex("^[A-Za-z0-9]{32}$", password.result)) &&
      azurerm_key_vault_secret.keycloak_client[name].value == password.result
    ])
    error_message = "Each vault secret must receive its generated 32-character alphanumeric credential."
  }

  assert {
    condition     = length(toset([for password in random_password.keycloak_client : password.result])) == 5
    error_message = "All five credentials must be independent."
  }
}

run "retain_keycloak_secrets" {
  command = plan

  module {
    source = "./keyvault"
  }

  assert {
    condition = alltrue([
      for name, password in random_password.keycloak_client :
      can(regex("^[A-Za-z0-9]{32}$", password.result)) &&
      azurerm_key_vault_secret.keycloak_client[name].value == password.result
    ])
    error_message = "Subsequent plans must retain known credentials rather than generate replacements."
  }
}