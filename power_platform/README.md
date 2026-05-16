# Power Platform — Incident Approval Flow

## Overview

A Power Automate cloud flow that triggers when the AI-Ops monitor emits a
`DriftThresholdExceeded` alert to an Azure Service Bus queue.

## Flow Steps

1. **Trigger**: Service Bus message received on `drift-alerts` queue.
2. **Parse JSON**: Extract `feature`, `score`, `threshold`, `pipeline_run_id`.
3. **Post Adaptive Card**: Send an Adaptive Card to the `#ops-alerts` Teams channel
   with drift details and two actions: **Approve rollback** / **Dismiss**.
4. **Wait for response** (timeout: 4 hours).
5. **Branch on decision**:
   - *Approve rollback*: Call the Fabric REST API to cancel the pipeline run
     and trigger a re-run from the previous day's Silver snapshot.
   - *Dismiss*: Log the dismissal reason to the Log Analytics workspace via
     the Data Collector API and complete the Service Bus message.
6. **Notify**: Post the outcome back to Teams.

## Deployment

Export the flow as a solution (`incident_approval_flow.json`) and import
into the target Power Platform environment via `pac solution import`.

The Service Bus connection uses a Managed Identity connector so no
shared-access-policy keys are stored in the flow.

## Security

- The Fabric REST API call uses an Entra service principal whose secret is
  stored in Key Vault and fetched via the Key Vault connector.
- Approvers are restricted to members of the `ops-admins` Entra group.
