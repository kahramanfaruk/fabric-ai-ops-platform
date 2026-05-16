# Runbook

## Deploy Infrastructure

```bash
az group create --name rg-fab-aiops-dev --location germanywestcentral
az deployment group create \
  --resource-group rg-fab-aiops-dev \
  --template-file infra/bicep/main.bicep \
  --parameters environment=dev adminGroupObjectId=<your-group-object-id>
```

## Run Pipeline Locally (unit-test mode)

```bash
pip install -e ".[dev]"
make test
```

## Trigger Fabric Pipeline via REST

```python
import requests
from azure.identity import DefaultAzureCredential

token = DefaultAzureCredential().get_token("https://api.fabric.microsoft.com/.default").token
requests.post(
    f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/items/{PIPELINE_ID}/jobs/instances",
    headers={"Authorization": f"Bearer {token}"},
    json={"executionData": {"parameters": {"partition_date": "2024-03-15"}}},
)
```

## Check Drift Alerts

Drift metrics are emitted to Azure Monitor under the namespace
`fabric-ai-ops-platform.aiops`.  Create an alert rule in the Azure Portal:
- Metric: `drift.psi`
- Threshold: > 0.2
- Aggregation: Maximum, 5-minute window
- Action: trigger the Service Bus queue that feeds the Power Automate flow.

## Rotate AI Search Query Key

1. Generate a new query key in the Azure Portal → AI Search → Keys.
2. Update the Key Vault secret `aisearch-query-key` with the new value.
3. Old key remains valid until the `lru_cache` in `secret_client.py`
   expires (process restart) — plan a rolling restart if immediate
   revocation is required.
