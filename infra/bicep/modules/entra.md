# Entra ID Design

## Identity Model

| Identity | Type | Purpose | Roles |
|---|---|---|---|
| `fabric-ai-ops-platform-mi` | User-assigned Managed Identity | Fabric pipelines & notebooks | Fabric Contributor, Key Vault Secrets User |
| `fabric-ai-ops-platform-sp` | Service Principal | Azure DevOps CI/CD deployments | Contributor (resource group), Key Vault Secrets Officer |
| `ops-admins` | Entra Group | Human operators | Key Vault Secrets Officer, AI Search Contributor |
| `ops-readers` | Entra Group | Read-only stakeholders | Reader, AI Search Index Data Reader |

## Principles

- **No client secrets in pipelines.** CI uses federated identity credentials (OIDC) from
  Azure DevOps → Service Principal.  No password rotation required.
- **Least privilege.** Each identity holds the minimum roles needed.
  The managed identity never holds `Contributor` — it only reads secrets and writes
  to Fabric.
- **No permanent standing access.** Privileged roles (Owner, Key Vault Secrets Officer)
  are assigned to Entra groups via PIM with just-in-time activation.
- **Conditional Access.** All interactive users accessing the Azure Portal are gated
  on MFA + compliant-device policy.
