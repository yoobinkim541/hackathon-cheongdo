param environmentName string
param location string
param aiServicesLocation string
param enableAiServices bool
@secure()
param copilotGithubToken string
param alertEmail string
param copilotModel string
param webAppExists bool
param webImageName string
param tags object

var token = toLower(uniqueString(subscription().id, resourceGroup().id, environmentName))
var webName = 'ca-web-${token}'
var secretName = 'copilot-github-token'

var roleAcrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var roleKeyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${token}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${token}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-web-${token}'
  location: location
  tags: tags
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'cr${token}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, roleAcrPull)
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrPull)
  }
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${token}'
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
  }
}

resource vaultSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: secretName
  properties: {
    value: copilotGithubToken
  }
}

resource kvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, identity.id, roleKeyVaultSecretsUser)
  scope: vault
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleKeyVaultSecretsUser)
  }
}

module ai 'ai.bicep' = if (enableAiServices) {
  name: 'ai-services'
  params: {
    name: 'ai-${token}'
    location: aiServicesLocation
    tags: tags
    principalId: identity.properties.principalId
  }
}

var aiEndpoint = enableAiServices ? ai!.outputs.endpoint : ''

resource containerEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${token}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

module existingImage 'fetch-image.bicep' = {
  name: 'web-existing-image'
  params: {
    exists: webAppExists
    name: webName
  }
}

var image = empty(existingImage.outputs.image) ? webImageName : existingImage.outputs.image

resource web 'Microsoft.App/containerApps@2024-03-01' = {
  name: webName
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    environmentId: containerEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        // Runs live in process memory; affinity keeps a browser's SSE stream and approval on the replica that owns the run.
        stickySessions: {
          affinity: 'sticky'
        }
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: identity.id
        }
      ]
      secrets: [
        {
          name: secretName
          keyVaultUrl: '${vault.properties.vaultUri}secrets/${secretName}'
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: image
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'COPILOT_GITHUB_TOKEN', secretRef: secretName }
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'AZURE_AI_ENDPOINT', value: aiEndpoint }
            { name: 'ENABLE_AI_SERVICES', value: string(enableAiServices) }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
            { name: 'COPILOT_MODEL', value: copilotModel }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/healthz', port: 8000 }
              initialDelaySeconds: 10
              periodSeconds: 30
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: { path: '/readyz', port: 8000 }
              initialDelaySeconds: 5
              periodSeconds: 10
              failureThreshold: 6
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-concurrency'
            http: {
              metadata: {
                concurrentRequests: '20'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    acrPull
    kvSecretsUser
    vaultSecret
  ]
}

var webFqdn = web.properties.configuration.ingress.fqdn

module alerts 'alerts.bicep' = {
  name: 'alerts'
  params: {
    token: token
    location: location
    tags: tags
    appInsightsId: appInsights.id
    healthUrl: 'https://${webFqdn}/healthz'
    alertEmail: alertEmail
  }
}

output registryEndpoint string = registry.properties.loginServer
output registryName string = registry.name
output containerEnvironmentName string = containerEnv.name
output webName string = web.name
output webEndpointUrl string = 'https://${webFqdn}'
output aiEndpoint string = aiEndpoint
output keyVaultName string = vault.name
output identityClientId string = identity.properties.clientId
output appInsightsConnectionString string = appInsights.properties.ConnectionString
