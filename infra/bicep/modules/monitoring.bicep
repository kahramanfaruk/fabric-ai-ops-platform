// Log Analytics Workspace + Application Insights module.
// Both are free tier within student subscription monthly limits.

param name string
param location string
param environment string

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${name}-law'
  location: location
  tags: { environment: environment, workload: 'fabric-ai-ops-platform' }
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30    // Minimise cost; increase in prod.
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${name}-appi'
  location: location
  kind: 'web'
  tags: { environment: environment, workload: 'fabric-ai-ops-platform' }
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

output workspaceId string = law.id
output appInsightsConnectionString string = appInsights.properties.ConnectionString
