# Architecture

## Data Flow

```
Raw Sources (JSON/CSV/Parquet)
        │
        ▼
[Bronze Delta Table]  ← append-only, raw, audit trail
        │  silver_transform.py (dedup, type-cast, JSON parse)
        ▼
[Silver Delta Table]  ← cleansed, row-level, upsert idempotent
        │  gold_aggregate.py (daily partition, replaceWhere)
        ▼
[Gold Delta Table]    ← aggregated, query-optimised, Z-ordered
        │
        ├──► Fabric SQL Endpoint → Power BI Direct Lake
        │
        └──► AI Search Indexer (indexer.py) → Operations Index
                    │
                    ▼
              RAG Chain (rag_chain.py)
                    │
                    ▼
            Operations Assistant (assistant.py)
```

## Component Map

| Component | Technology | Notes |
|---|---|---|
| Lakehouse | Microsoft Fabric OneLake / Delta | Medallion: Bronze/Silver/Gold |
| Orchestration | Fabric Data Pipeline (notebook activity) | `orchestrator.py` as entry point |
| SQL Analytics | Fabric SQL Endpoint + semantic model | Direct Lake mode for Power BI |
| Secret Store | Azure Key Vault (Standard, RBAC) | No secrets in code or env vars |
| Search | Azure AI Search (Free tier) | Hybrid: BM25 + vector |
| LLM | Azure OpenAI (GPT-4o) | Managed identity, no key |
| Drift detection | scipy (PSI + KS + Wasserstein) | `drift_detector.py` |
| Evaluation | Judge LLM (same GPT-4o deployment) | `evaluator.py` |
| Monitoring | Azure Monitor + OpenTelemetry | Custom metrics: drift, eval scores |
| Identity | Entra ID Managed Identity | Workload identity for all Azure calls |
| CI/CD | GitHub Actions (Azure DevOps for enterprise) | Lint + typecheck + test + deploy |
| Approvals | Power Automate + Teams Adaptive Card | Drift rollback approval flow |

## Security Controls

- All secrets in Key Vault; rotated via automated policy.
- Managed identity for all service-to-service calls (no credential leakage).
- Private endpoint on Key Vault (public access disabled).
- Bicep enforces purge protection and soft-delete on Key Vault.
- RBAC on all resources; access policies disabled.
- Gitleaks secret scanning on every PR.
- Fabric workspace restricted to licensed Entra group members.
