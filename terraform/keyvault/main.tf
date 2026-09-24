# Resolves the Terraform SP's tenant/object id and the RBAC-eligible principal for self-assignment.
data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "instance" {
  name     = "velotime-infra-${var.basename}"
  location = var.location
}

resource "azurerm_key_vault" "instance" {
  name                       = "velotime-${var.basename}"
  resource_group_name        = azurerm_resource_group.instance.name
  location                   = azurerm_resource_group.instance.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = var.termination_protection
  soft_delete_retention_days = 90
}

resource "azurerm_role_assignment" "terraform_secrets_officer" {
  scope                = azurerm_key_vault.instance.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "eso_secrets_user" {
  scope                            = azurerm_key_vault.instance.id
  role_definition_name             = "Key Vault Secrets User"
  principal_id                     = var.eso_principal_object_id
  skip_service_principal_aad_check = true
}

# RBAC role assignments take time to propagate; wait before writing secrets on first apply.
resource "time_sleep" "rbac_propagation" {
  depends_on = [
    azurerm_role_assignment.terraform_secrets_officer
  ]

  create_duration = "30s"
}

resource "azurerm_key_vault_secret" "cache_host" {
  name         = "velotime-cache-host"
  value        = var.cache_host
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "cache_port" {
  name         = "velotime-cache-port"
  value        = var.cache_port
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "cache_username" {
  name         = "velotime-cache-username"
  value        = var.cache_username
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "cache_password" {
  name         = "velotime-cache-password"
  value        = var.cache_password
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "database_host" {
  name         = "velotime-database-host"
  value        = var.database_host
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "database_port" {
  name         = "velotime-database-port"
  value        = var.database_port
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "database_username" {
  name         = "velotime-database-user"
  value        = var.database_username
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "database_password" {
  name         = "velotime-database-password"
  value        = var.database_password
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "keycloak_database_host" {
  name         = "keycloak-database-host"
  value        = var.keycloak_database_host
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "keycloak_database_port" {
  name         = "keycloak-database-port"
  value        = var.keycloak_database_port
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "keycloak_database_name" {
  name         = "keycloak-database-name"
  value        = var.keycloak_database_name
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "keycloak_database_username" {
  name         = "keycloak-database-user"
  value        = var.keycloak_database_username
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "keycloak_database_password" {
  name         = "keycloak-database-password"
  value        = var.keycloak_database_password
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "keycloak_database_admin_database" {
  name         = "keycloak-database-admin-database"
  value        = var.keycloak_database_admin_database
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "keycloak_database_admin_username" {
  name         = "keycloak-database-admin-user"
  value        = var.keycloak_database_admin_username
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}

resource "azurerm_key_vault_secret" "keycloak_database_admin_password" {
  name         = "keycloak-database-admin-password"
  value        = var.keycloak_database_admin_password
  key_vault_id = azurerm_key_vault.instance.id
  depends_on   = [time_sleep.rbac_propagation]
}
