# Fabric AI Ops Platform

> Production-grade Data & AI platform on Microsoft Fabric + Azure.
> Medallion Lakehouse (Bronze/Silver/Gold) · Azure OpenAI RAG assistant · Statistical AI-Ops · CI/CD

---

## Stack

| Layer | Technology |
|---|---|
| **Lakehouse (Medallion)** | Microsoft Fabric OneLake, Delta Lake, PySpark |
| **Data Sources** | Azure Open Datasets — NYC Taxi TLC + NOAA Weather (zero-cost, Microsoft-hosted) |
| **Data Engineering** | PySpark, Python 3.11+, pandas |
| **SQL Analytics** | Fabric SQL Endpoint, Direct Lake (Power BI) |
| **Secret Management** | Azure Key Vault — RBAC, private endpoint, purge protection |
| **Vector + Keyword Search** | Azure AI Search — hybrid BM25 + vector (RRF) |
| **GenAI Assistant** | Azure OpenAI GPT-4o, grounded RAG chain |
| **AI-Ops** | PSI + KS + Wasserstein drift detection, judge-LLM evaluation |
| **Identity** | Entra ID Managed Identity, OIDC federated credential for CI |
| **Monitoring** | Azure Monitor, OpenTelemetry SDK, Log Analytics |
| **CI/CD** | GitHub Actions — lint · mypy strict · pytest · Gitleaks · conventional commits |
| **Approvals** | Power Automate + Teams Adaptive Cards — drift rollback flow |
| **IaC** | Azure Bicep — Key Vault, AI Search, Log Analytics |

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/your-org/fabric-ai-ops-platform.git
cd fabric-ai-ops-platform
pip install -e ".[dev]"

# 2. Configure environment
cp .env.example .env
# Fill in: AZURE_TENANT_ID, KEYVAULT_URL, AISEARCH_ENDPOINT, OPENAI_ENDPOINT,
#          FABRIC_WORKSPACE_ID, LAKEHOUSE_NAME

# 3. Deploy Azure infrastructure
az group create --name rg-fabric-aiops-dev --location germanywestcentral
az deployment group create \
  --resource-group rg-fabric-aiops-dev \
  --template-file infra/bicep/main.bicep \
  --parameters environment=dev adminGroupObjectId=<entra-group-object-id>

# 4. Create OneLake shortcuts (one-time, in Fabric Portal)
#    Lakehouse → New shortcut → Azure Data Lake Storage Gen2
#    Account: azureopendatastore.blob.core.windows.net
#    Containers: nyctlc/yellow, nyctlc/green, isd/

# 5. Run CI locally
make ci   # lint + typecheck + tests
```

---

## Project Structure

```
src/
  common/         Config (pydantic-settings), logging, exceptions, schemas
  azure/          Key Vault client · AI Search client + indexer
  fabric/
    lakehouse/    Bronze ingest · Silver transform · Gold aggregate
                  schema_registry.py · data_sources.py (Azure Open Datasets)
    pipelines/    Orchestrator (Bronze → Silver → Gold → drift check)
    sql_analytics/ Gold views (Fabric SQL Endpoint) · semantic model queries
  genai/          RAG chain · Operations assistant · Prompt templates
  aiops/          Drift detector (PSI/KS/Wasserstein) · LLM evaluator · Monitor
tests/
  unit/           Drift detector · RAG chain · Key Vault · Bronze ingest
  integration/    AI Search integration
infra/bicep/      Key Vault · AI Search · Log Analytics + App Insights · Entra design
.github/          CI workflow · PR checks (Gitleaks · conventional commits)
power_platform/   Incident approval flow spec (Teams Adaptive Card + rollback)
notebooks/        01 Bronze exploration · 02 Silver QA · 03 Gold analytics · 04 Drift analysis
docs/             Architecture · Security (STRIDE) · Cost governance · Runbook
```

---

## Data Sources

Both datasets are **Microsoft-hosted, always free**, accessed via **OneLake Shortcut** so
all data stays under Fabric governance, lineage, and access control.

| Dataset | Path | Key Features |
|---|---|---|
| NYC Taxi Yellow / Green (TLC) | `wasbs://nyctlc@azureopendatastore.blob.core.windows.net/` | `fareAmount`, `tripDistance`, `tipAmount`, `passengerCount` — ~50M rows/year |
| NOAA ISD Weather | `wasbs://isd@azureopendatastore.blob.core.windows.net/` | `temperature`, `windSpeed`, `precipDepth` — joined with taxi at Gold layer |

**Drift detection story**: comparing `fareAmount` distribution for 2022 (reference baseline)
vs 2023 (current) surfaces real distributional shift caused by post-COVID fare recovery
and fuel price changes — PSI fires above 0.2 authentically on real data.

---

## Architecture

```
Azure Open Datasets (wasbs://)  ←──  OneLake Shortcut (ABFSS)
              │
              ▼
   [Bronze Delta]  append-only · ACID · time-travel audit
              │  silver_transform.py — dedup, type-cast, SHA-256 trip_id
              ▼
   [Silver Delta]  MERGE upsert · exactly-once semantics
              │  gold_aggregate.py — replaceWhere partition · weather join
              ▼
   [Gold Delta]    query-optimised · Z-ordered on (taxi_type, pu_location_id)
              │
              ├──► Fabric SQL Endpoint → Power BI Direct Lake
              │
              └──► AI Search Indexer → Hybrid Index (BM25 + vector)
                           └──► RAG Chain → Operations Assistant (GPT-4o)
                                      └──► Judge LLM Evaluation → Azure Monitor
```

---

## Security

See `docs/security_design.md` for the full STRIDE threat model.

- **No credentials in source code or environment variables.** All secrets in Key Vault,
  accessed at runtime via managed identity.
- Key Vault: public access disabled, RBAC authorization, purge protection enabled.
- CI/CD uses OIDC federated identity — no client secrets, no rotation.
- Gitleaks secret scan runs on every pull request.

---

## Cost (Azure Student Subscription — €85 / 12 months)

Designed to run within free-tier limits. Estimated annual spend: **< €5**
(Azure OpenAI token usage only). See `docs/cost_governance.md`.

---

## License

MIT
