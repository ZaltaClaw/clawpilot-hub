---
name: "msx-crm"
description: "Query Microsoft Sales Experience (MSX) CRM data — accounts, opportunities, milestones, tasks, and deal teams. Triggers: any mention of 'MSX', 'CRM', 'milestones', 'opportunities', 'deal team', 'pipeline', 'accounts', 'customer milestones', 'sales play', or questions about customer engagement status in Dynamics 365 Sales. Also triggers for: listing active milestones, finding milestones needing tasks, checking opportunity status, or any MCAPS/sales-related queries."
author: "roey zalta"
version: "1.0.1"
tags: [msx, crm, dynamics365, sales, mcaps]
category: "Sales & Demos"
---

# MSX CRM Skill

## When to use this skill
Use when the user asks anything about Microsoft Sales Experience (MSX) data: accounts, opportunities, milestones, tasks, deal team, pipeline, "my active milestones", "milestones needing tasks", customer engagement status, or any MCAPS/sales-related query that maps to Dynamics 365 Sales. Also use when they reference TPIDs, opportunity IDs, or want raw OData against CRM entity sets.

## Overview
This skill queries the Microsoft Sales Experience (MSX) CRM (Dynamics 365) to retrieve accounts, opportunities, milestones, tasks, and deal team data. It uses a helper script at `~/.copilot/skills/msx-crm/run-tool.mjs`.

## CRM URL
https://microsoftsales.crm.dynamics.com

## Prerequisites
- **VPN must be connected** — CRM is only accessible on corpnet
- Node.js (any recent LTS, e.g. 18+)
- Azure CLI (`az`) must be logged in for authentication (`az login`)

## How to Run Tools
```bash
node ~/.copilot/skills/msx-crm/run-tool.mjs <tool-name> '<json-params>'
```

## Available Tools

### 1. `crm_auth_status`
Check if CRM authentication is working.
```bash
node ~/.copilot/skills/msx-crm/run-tool.mjs crm_auth_status
```

### 2. `crm_whoami`
Get the current user's CRM identity.
```bash
node ~/.copilot/skills/msx-crm/run-tool.mjs crm_whoami
```

### 3. `get_milestones`
Get milestones for a customer, opportunity, or the current user.
Parameters:
- `customerKeyword` (string) — Search accounts by name (e.g., "Aidoc", "Nuvei")
- `opportunityKeyword` (string) — Search opportunities by name
- `opportunityId` (GUID) — Single opportunity ID
- `opportunityIds` (GUID[]) — Multiple opportunity IDs
- `milestoneNumber` (string) — Milestone number lookup
- `milestoneId` (GUID) — Direct milestone lookup
- `ownerId` (GUID) — Filter by owner
- `mine` (boolean) — Get milestones owned by current user
- `statusFilter` ("active") — Only active milestones (Not Started, On Track, In Progress, Blocked, At Risk)
- `keyword` (string) — Filter milestone names
- `includeTasks` (boolean) — Include task data

Examples:
```bash
# Customer milestones
node ~/.copilot/skills/msx-crm/run-tool.mjs get_milestones '{"customerKeyword":"Aidoc"}'

# My active milestones
node ~/.copilot/skills/msx-crm/run-tool.mjs get_milestones '{"mine":true,"statusFilter":"active"}'

# Active milestones for a customer
node ~/.copilot/skills/msx-crm/run-tool.mjs get_milestones '{"customerKeyword":"Nuvei","statusFilter":"active"}'
```

### 4. `list_opportunities`
List opportunities for a customer.
Parameters:
- `customerKeyword` (string) — Search accounts by name
- `accountIds` (GUID[]) — Direct account IDs
- `includeCompleted` (boolean) — Include completed/old opportunities

```bash
node ~/.copilot/skills/msx-crm/run-tool.mjs list_opportunities '{"customerKeyword":"Aidoc"}'
```

### 5. `get_my_active_opportunities`
Get all active opportunities where the user is owner or deal team member.
Parameters:
- `customerKeyword` (string) — Optional filter by customer name

```bash
node ~/.copilot/skills/msx-crm/run-tool.mjs get_my_active_opportunities
node ~/.copilot/skills/msx-crm/run-tool.mjs get_my_active_opportunities '{"customerKeyword":"Aidoc"}'
```

### 6. `get_milestone_activities`
Get tasks linked to milestones.
Parameters:
- `milestoneId` (GUID) — Single milestone
- `milestoneIds` (GUID[]) — Multiple milestones

```bash
node ~/.copilot/skills/msx-crm/run-tool.mjs get_milestone_activities '{"milestoneId":"abc-123..."}'
```

### 7. `find_milestones_needing_tasks`
Find active milestones that have no tasks created yet.
Parameters:
- `customerKeyword` (string)
- `opportunityKeyword` (string)
- `mine` (boolean)

```bash
node ~/.copilot/skills/msx-crm/run-tool.mjs find_milestones_needing_tasks '{"mine":true}'
```

### 8. `crm_query`
Raw OData query against any CRM entity set.
Parameters:
- `entitySet` (string, required) — e.g., "accounts", "opportunities", "msp_engagementmilestones", "tasks"
- `filter` (string) — OData $filter expression
- `select` (string) — Comma-separated fields
- `orderby` (string) — OData $orderby expression
- `top` (number) — Max records
- `expand` (string) — OData $expand expression

```bash
node ~/.copilot/skills/msx-crm/run-tool.mjs crm_query '{"entitySet":"accounts","filter":"contains(name,'\''Aidoc'\'')","select":"accountid,name,msp_tpid","top":10}'
```

### 9. `crm_get_record`
Get a single record by entity set and ID.
Parameters:
- `entitySet` (string, required)
- `id` (GUID, required)
- `select` (string) — Comma-separated fields

### 10. `list_accounts_by_tpid`
Find accounts by TPID.
Parameters:
- `tpid` (string, required)

## Formatted Value Pattern
CRM returns lookup display names as `field@OData.Community.Display.V1.FormattedValue`. When presenting data, always check for these formatted values to show human-readable names instead of GUIDs.

## Error Handling
- If you get "IP address is blocked" → VPN is not connected. Tell the user.
- If you get auth errors → Run `az login` or check Azure CLI session.
- Always wrap calls in try/catch and surface useful error messages.

## Output Formatting
When presenting CRM data to the user:
- Use tables for lists of milestones/opportunities
- Show status with emoji indicators: ✅ Completed, 🟢 On Track, 🔴 At Risk/Lost, ❌ Cancelled, ⏸️ Not Started, 🔄 In Progress, ⚠️ Blocked
- Include relevant dates, owners, and opportunity names
- Summarize counts at the end
