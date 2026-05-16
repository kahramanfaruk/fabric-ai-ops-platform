// Main Bicep deployment entry point.
// All sensitive outputs (keys, connection strings) are written to Key Vault,
// never returned as plaintext ARM outputs.
//
// Deploy with:
//   az deployment sub create --location germanywestcentral --template-file main.bicep \
//     --parameters @main.parameters.json

targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = 'germanywestcentral'

@description('Environment tag: dev | test | prod.')
@allowed(['dev', 'test', 'prod'])
param environment string = 'dev'

@description('Object ID of the Entra group that will be Key Vault Secrets Officer.')
param adminGroupObjectId string

var prefix = 'fab-aiops-${environment}'

module kv 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    name: '${prefix}-kv'
    location: location
    adminGroupObjectId: adminGroupObjectId
    environment: environment
  }
}

module search 'modules/aisearch.bicep' = {
  name: 'aisearch'
  params: {
    name: '${prefix}-search'
    location: location
    keyVaultName: kv.outputs.keyVaultName
    environment: environment
  }
}

module monitor 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    name: '${prefix}-monitor'
    location: location
    environment: environment
  }
}

output keyVaultUrl string = kv.outputs.keyVaultUrl
output searchEndpoint string = search.outputs.endpoint
output logAnalyticsWorkspaceId string = monitor.outputs.workspaceId
