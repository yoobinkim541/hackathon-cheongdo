targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('azd environment name; used to derive resource names.')
param environmentName string

@minLength(1)
@description('Primary region for all resources.')
param location string = 'koreacentral'

@description('Region for Azure AI Services. Empty means the primary region.')
param aiServicesLocation string = ''

@description('Create Azure AI Services (OCR, speech) and its role assignment.')
param enableAiServices bool = false

@secure()
@description('GitHub token for the Copilot SDK, stored in Key Vault.')
param copilotGithubToken string

@description('Email for alert notifications. Empty creates alerts without actions.')
param alertEmail string = ''

@description('Model name passed to the Copilot SDK.')
param copilotModel string = 'claude-sonnet-5'

@description('Set by azd when the web container app already exists.')
param webAppExists bool = false

@description('Initial image used before the first azd deploy.')
param webImageName string = 'mcr.microsoft.com/k8se/quickstart:latest'

var tags = { 'azd-env-name': environmentName }

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'modules/resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    environmentName: environmentName
    location: location
    aiServicesLocation: empty(aiServicesLocation) ? location : aiServicesLocation
    enableAiServices: enableAiServices
    copilotGithubToken: copilotGithubToken
    alertEmail: alertEmail
    copilotModel: copilotModel
    webAppExists: webAppExists
    webImageName: webImageName
    tags: tags
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.registryEndpoint
output AZURE_CONTAINER_REGISTRY_NAME string = resources.outputs.registryName
output AZURE_CONTAINER_ENVIRONMENT_NAME string = resources.outputs.containerEnvironmentName
output SERVICE_WEB_NAME string = resources.outputs.webName
output SERVICE_WEB_ENDPOINT_URL string = resources.outputs.webEndpointUrl
output AZURE_AI_ENDPOINT string = resources.outputs.aiEndpoint
output AZURE_KEY_VAULT_NAME string = resources.outputs.keyVaultName
output AZURE_CLIENT_ID string = resources.outputs.identityClientId
output APPLICATIONINSIGHTS_CONNECTION_STRING string = resources.outputs.appInsightsConnectionString
