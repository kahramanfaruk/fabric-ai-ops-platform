// Azure AI Search module.
// Free tier (F) fits within student subscription limits (3 indexes, 50 MB).
// Query key is stored in Key Vault, not returned as an ARM output.

param name string
param location string
param keyVaultName string
param environment string

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: name
  location: location
  tags: { environment: environment, workload: 'fabric-ai-ops-platform' }
  sku: { name: 'free' }         // Student subscription: free tier
  properties: {
    replicaCount: 1
    partitionCount: 1
    publicNetworkAccess: 'enabled'   // Free tier does not support private endpoints
    disableLocalAuth: false
  }
}

// Persist admin key in Key Vault so application code never reads it from ARM.
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource queryKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'aisearch-query-key'
  properties: {
    value: search.listQueryKeys().value[0].key
    attributes: { enabled: true }
  }
}

output endpoint string = 'https://${search.name}.search.windows.net'
