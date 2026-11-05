param token string
param location string
param tags object
param appInsightsId string
param healthUrl string
param alertEmail string

var webTestName = 'webtest-healthz-${token}'
var hasEmail = !empty(alertEmail)

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (hasEmail) {
  name: 'ag-${token}'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'dongheng'
    enabled: true
    emailReceivers: [
      {
        name: 'team'
        emailAddress: alertEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

var actionGroupIds = hasEmail ? [actionGroup.id] : []

resource webTest 'Microsoft.Insights/webtests@2022-06-15' = {
  name: webTestName
  location: location
  tags: union(tags, { 'hidden-link:${appInsightsId}': 'Resource' })
  kind: 'standard'
  properties: {
    SyntheticMonitorId: webTestName
    Name: 'healthz'
    Enabled: true
    Frequency: 300
    Timeout: 30
    Kind: 'standard'
    RetryEnabled: true
    Locations: [
      { Id: 'apac-jp-kaw-edge' }
      { Id: 'apac-hk-hkn-azr' }
      { Id: 'apac-sg-sin-azr' }
    ]
    Request: {
      RequestUrl: healthUrl
      HttpVerb: 'GET'
      ParseDependentRequests: false
    }
    ValidationRules: {
      ExpectedHttpStatusCode: 200
      SSLCheck: true
      SSLCertRemainingLifetimeCheck: 7
    }
  }
}

resource availabilityAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-availability-${token}'
  location: 'global'
  tags: tags
  properties: {
    description: '/healthz availability below 100%'
    severity: 1
    enabled: true
    scopes: [appInsightsId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'availability'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'availabilityResults/availabilityPercentage'
          operator: 'LessThan'
          threshold: 100
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [for id in actionGroupIds: { actionGroupId: id }]
  }
  dependsOn: [webTest]
}

resource serverErrorAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'alert-5xx-${token}'
  location: location
  tags: tags
  properties: {
    displayName: 'HTTP 5xx responses'
    description: '5 or more 5xx requests within 5 minutes'
    severity: 2
    enabled: true
    scopes: [appInsightsId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      allOf: [
        {
          query: 'requests | where toint(resultCode) >= 500'
          timeAggregation: 'Count'
          operator: 'GreaterThanOrEqual'
          threshold: 5
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: actionGroupIds
    }
  }
}

resource rateLimitAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'alert-rate-limit-${token}'
  location: location
  tags: tags
  properties: {
    displayName: 'Copilot rate limit'
    description: 'Any Copilot rate-limit failure (fixed log message copilot_rate_limited) within 5 minutes'
    severity: 2
    enabled: true
    scopes: [appInsightsId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      allOf: [
        {
          query: 'traces | where message startswith "copilot_rate_limited"'
          timeAggregation: 'Count'
          operator: 'GreaterThanOrEqual'
          threshold: 1
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: actionGroupIds
    }
  }
}
