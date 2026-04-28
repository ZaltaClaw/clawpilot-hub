---
name: EA Discount List
description: Build a per-customer Excel deliverable that lists Azure EA part numbers (one tab per service) with NetPrice, ERP, and the seller-requested discount % + post-discount price for the Deal Desk. Driven by the /azure-price skill.
version: 1.0.0
author: MCAPS Israel
category: Sales & Demos
tags: [Azure, EA, Pricing, Discount, Deal Desk, Excel, Sales]
compatible: [ClawPilot, Claude Code, Cursor, GitHub Copilot]
---

# /ea-discount-list — Azure EA discount sheet builder

## Purpose

Help Azure sellers / SEs produce a customer-ready Excel deliverable that lists Azure EA part numbers (one tab per service), shows the EA NetPrice and ERP, and adds the requested discount % + post-discount price the seller intends to ask the Deal Desk for.

## Prerequisite

This skill **requires the [`/azure-price`](../azure-price/SKILL.md) skill** to be installed and a current snapshot cached (`download_e6.py` to refresh).

## Modes

### Mode A — Interactive

When the user invokes the skill without an input spec file, walk them through:

1. **Customer name** (used in output filename: `<Customer>_EA_DiscountList_<YYYY-MM>.xlsx`).
2. **Services** — one tab per service. For each service collect:
   - **Service / search keywords** (e.g. "Cosmos DB", "Blob Storage Hot", "Defender for Servers", "GitHub", "App Gateway v2", "NAT Gateway", "Managed Disks").
     - Map to ProductFamily and/or ItemName ILIKE filters via the azure-price skill.
   - **Regions** (optional). Accept short suffixes like `US E, EU N, IL C, AE N, AP SE, AU E, BR S, Global`. If empty → all regions. If "Global" → only SKUs with no region suffix.
   - **Tier / extra filters** (optional, e.g. "Hot only", "Std P2 only", "exclude US G/N/S gov clouds"). Default: exclude `-US G`, `-US N`, `-US S` gov-cloud variants unless the seller explicitly asks for them.
   - **Discount %** (e.g. 30 for 30%).
3. Confirm the plan back as a table (service → region scope → discount %), then build.

Use your agent's confirmation primitive (e.g. `m_ask_user`) for any ambiguous yes/no choice; otherwise just collect inline.

### Mode B — From spec file

If the user provides a spec file (CSV/XLSX), expect columns:

| Sheet | Service | Keywords | ProductFamily | Regions | ExtraFilter | Discount% |
|---|---|---|---|---|---|---|
| Cosmos_DB | Azure Cosmos DB | cosmos | (optional exact) | US E, EU N | | 30 |
| Blob_Storage | Blob Storage Hot | blob storage hot | | Global | hot only | 30 |
| Defender | Defender for Cloud + Servers | defender | MCA MS Defender CSPM, MCA MS Defender for Containers, Azure Security Center | Global | servers + cspm + containers | 35 |
| GitHub | GitHub | github | | | | 35 |

Skip rows where `Sheet` is blank.

## Data source

All price data comes from the **`/azure-price`** skill (DuckDB over the EA Parquet snapshot).

Always use:
```bash
python3 ~/.copilot/skills/azure-price/query.py --sql "<SQL>" --format csv
```

The view is `prices`. Key columns: `PartNumber, ItemName, ProductFamily, ProductType, PurchaseUnit, Level, NetPrice, ERP, StartDate, EndDate`.

Filtering rules (always apply):
- `StartDate >= '<current month start>'` (or `StartDate <= CURRENT_DATE AND EndDate > CURRENT_DATE` if you want strictly current).
- Default-exclude gov clouds: `ItemName NOT ILIKE '%-US G%' AND ItemName NOT ILIKE '%-US N' AND ItemName NOT ILIKE '%-US N %' AND ItemName NOT ILIKE '%-US S%'`.
- Dedupe by PartNumber within each tab.

## Region detection

For services with regional SKUs, parse the trailing region suffix from `ItemName` (last `-` segment). Recognised values:
```
US E, US E2, US C, US W, US W2, US W3, US NC, US SC,
EU N, EU W, FR C, SE C, UK S, UK W, DE WC, CH N, NO E,
IL C, AE C, AE N, AP E, AP SE, AU E, AU SE,
BR S, CA E, IN C, IN S, IN W, KR C, ZA N
```
If no recognised suffix → label `Global`.

When the seller specifies regions, filter to `ItemName ILIKE '%-<region>'` for each requested region (OR'd together) PLUS any `-Global` rows when `Global` is requested.

## Output workbook

For every service tab:

| Col | Source |
|---|---|
| PartNumber | prices.PartNumber |
| ItemName | prices.ItemName |
| ProductFamily | prices.ProductFamily |
| ProductType | prices.ProductType |
| Region | parsed from ItemName |
| PurchaseUnit | prices.PurchaseUnit |
| Level | prices.Level |
| NetPrice (List) | prices.NetPrice |
| ERP | prices.ERP |
| StartDate | prices.StartDate |
| **RequestedDiscount%** | seller input, formatted `0%` |
| **RequestedNetPrice** | `NetPrice * (1 - Discount%)`, formatted `0.0000` |

Workbook conventions:
- Header row bold, freeze panes `A2`.
- Auto-size columns (cap at width 60).
- One **Summary** tab last with: Service, Tab name, Region scope, # SKUs, Discount %, Avg NetPrice, Avg RequestedNetPrice.

Save to: `Scratchpad/<Customer>_EA_DiscountList_<YYYY-MM>.xlsx` (or wherever the user specifies).

## Implementation pattern (Python via openpyxl + azure-price subprocess)

```python
import subprocess, csv, io, openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font
from pathlib import Path

QUERY_SCRIPT = Path.home() / ".copilot" / "skills" / "azure-price" / "query.py"

def query(sql):
    r = subprocess.run(
        ["python3", str(QUERY_SCRIPT), "--sql", sql, "--format", "csv"],
        capture_output=True, text=True, check=True)
    return list(csv.DictReader(io.StringIO(r.stdout)))

def build_where(keywords=None, product_families=None, regions=None,
                exclude_gov=True, extra_sql=None):
    clauses = ["StartDate >= '2026-01-01'"]
    if keywords:
        ors = " OR ".join([f"ItemName ILIKE '%{k}%'" for k in keywords])
        clauses.append(f"({ors})")
    if product_families:
        pf_list = ",".join([f"'{p}'" for p in product_families])
        clauses.append(f"ProductFamily IN ({pf_list})")
    if regions:
        ors = []
        for reg in regions:
            if reg.lower() == "global":
                ors.append("ItemName NOT SIMILAR TO '.*-(US E|US E2|US C|US W|...)$'")
            else:
                ors.append(f"ItemName ILIKE '%-{reg}'")
        clauses.append("(" + " OR ".join(ors) + ")")
    if exclude_gov:
        clauses.append("ItemName NOT ILIKE '%-US G%'")
        clauses.append("ItemName NOT ILIKE '%-US N'")
        clauses.append("ItemName NOT ILIKE '%-US N %'")
        clauses.append("ItemName NOT ILIKE '%-US S%'")
    if extra_sql:
        clauses.append(f"({extra_sql})")
    return " AND ".join(clauses)
```

For each service tab:
1. Build SQL with `build_where`, `SELECT DISTINCT PartNumber, ItemName, ProductFamily, ProductType, NetPrice, ERP, PurchaseUnit, Level, MAX(StartDate) AS StartDate FROM prices WHERE ... GROUP BY ... ORDER BY ProductFamily, ItemName`.
2. Dedupe by PartNumber (first wins).
3. Compute RequestedNetPrice = `round(NetPrice * (1 - discount/100), 6)`.
4. Write rows with formatting.

## Handling tricky inputs

- **"GitHub"** → `ProductFamily ILIKE '%GitHub%'`. ⚠️ GitHub Actions and GitHub Storage are billed via github.com, NOT Azure EA — they will not appear. Always warn the seller about this.
- **"Defender for Cloud"** → families: `MCA MS Defender CSPM`, `MCA MS Defender for Containers`, plus `Azure Security Center` filtered on `ItemName ILIKE '%Defender for Server%'` for Servers.
- **"Blob Storage Hot"** → `ItemName ILIKE '%Hot %'` AND `ProductFamily ILIKE '%Storage%'`. Confirm tier (Hot/Cool/Archive) with seller if not specified.
- **"Managed Disks"** → typically narrow further by tier (Premium SSD v1/v2, Standard SSD, Standard HDD, Ultra). Ask if scope is unclear.
- **MGN / Data Transfer** → small SKU set; consider showing the full list and letting the seller prune.
- **Reserved Instances** — by default only return pay-go (`PurchasePeriod IS NULL` or = 'Monthly'). Ask if RIs are needed.

## Validation before delivery

Before saving, print a summary to the user:
```
Sheet           Region scope         #SKUs   Discount    Avg List → Avg Requested
Cosmos_DB       US E, EU N            164      30%       $X.XX → $Y.YY
GitHub          Global                 13      35%       $X.XX → $Y.YY
Defender        Global                 15      35%       $X.XX → $Y.YY
...
```
Ask the seller to confirm before saving the final file.

## Filename + location

- Default: `Scratchpad/<Customer>_EA_DiscountList_<YYYY-MM>.xlsx`.
- If a customer engagement folder exists at `~/customer-engagements/<Customer>/`, offer to save there instead.

## Don't

- Do NOT include gov-cloud SKUs (US G / US N / US S) unless explicitly requested.
- Do NOT use prices outside the current month's snapshot unless the user asks.
- Do NOT silently invent SKUs — if `azure-price` returns 0 rows for a service, tell the seller and ask for refined keywords.
- Do NOT include the customer's source-of-truth document content if it's encrypted/MIP-protected; ask the seller to type the discount values instead.
