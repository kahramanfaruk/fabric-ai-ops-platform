# Security Design

## Threat Model (STRIDE summary)

| Threat | Control |
|---|---|
| **S**poofing (API impersonation) | Managed Identity; no shared secrets |
| **T**ampering (data at rest) | Delta ACID + Key Vault encryption at rest |
| **R**epudiation (who ran what) | Azure Monitor audit logs + pipeline run IDs |
| **I**nformation disclosure (secret leakage) | Gitleaks in CI; Key Vault public access disabled |
| **D**enial of Service (runaway costs) | Budget alerts; `max_tokens` caps on LLM calls |
| **E**scalation of privilege | RBAC least-privilege; PIM for privileged roles |

## Data Classification

| Layer | Classification | Encryption | Access |
|---|---|---|---|
| Bronze | Confidential (raw operational data) | AES-256 at rest (OneLake) | Pipeline MI only |
| Silver | Confidential | AES-256 at rest | Pipeline MI + data engineers |
| Gold | Internal | AES-256 at rest | Analysts, Power BI service principal |
| AI Search index | Internal | Service-managed | Query key in Key Vault |

## Compliance Notes

- GDPR: no personal data in scope for this demo.  Real deployments must
  classify PII columns and apply column-level encryption or masking.
- DSGVO: same as GDPR; applicable in German customer contexts.
- ISO 27001 alignment: documented access control (this file), audit logging
  (Monitor), change management (git + PR workflow).
