// Azure Key Vault module.
// Soft-delete and purge protection are mandatory for production workloads.
// RBAC authorization model is used; legacy access policies are disabled.

param name string
param location string
param adminGroupObjectId string
param environment string

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: { environment: environment, workload: 'fabric-ai-ops-platform' }
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true        // RBAC over access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true           // Immutable once set; protects data
    publicNetworkAccess: 'Disabled'       // Private endpoint only
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
  }
}

// Grant admin group 'Key Vault Secrets Officer' for secret management.
resource adminRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, adminGroupObjectId, 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
  scope: kv
  properties: {
    principalId: adminGroupObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'  // Key Vault Secrets Officer
    )
  }
}

output keyVaultName string = kv.name
output keyVaultUrl string = kv.properties.vaultUri
