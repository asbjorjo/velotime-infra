output "vault_id" {
  value = azurerm_key_vault.instance.id
}

output "vault_uri" {
  value = azurerm_key_vault.instance.vault_uri
}

output "resource_group_name" {
  value = azurerm_resource_group.instance.name
}
