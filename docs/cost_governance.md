# Cost & Governance

## Student Subscription Budget (€85 / 12 months)

| Service | SKU | Monthly Free Allowance | Estimated Usage | Cost |
|---|---|---|---|---|
| Key Vault | Standard | 10,000 ops | ~200 ops | €0 |
| AI Search | Free | 3 indexes, 50 MB | 1 index, ~5 MB | €0 |
| Azure Monitor | Free tier | varies | Basic metrics only | €0 |
| App Insights | Workspace-based | 5 GB/month | < 1 GB | €0 |
| Azure OpenAI | PAYG | — | ~100K tokens/month ≈ €0.20 | ~€2/year |
| Fabric | Free trial / F2 | — | Notebooks + Lakehouse | Trial period |
| GitHub Actions | Free | 2,000 min/month | ~200 min/month | €0 |

**Total estimated spend: < €5 over 12 months.**

## Cost Controls

- Azure Monitor budget alert at €10 (email + Teams notification).
- OpenAI usage capped via `max_tokens=512` in all completions.
- Log Analytics retention set to 30 days (minimum; increase for prod).
- AI Search free tier is sufficient for the index size in this project.
- Fabric F2 SKU can be paused when not in use to stop compute billing.
