---
name: Azure Price
description: Download the Microsoft Enterprise EA (E6) Azure price list directly from APT and run fast SQL queries over it locally with DuckDB. Includes a fully automated monthly refresh — no manual file handling.
version: 1.0.0
author: MCAPS Israel
category: Azure
tags: [Azure, Pricing, EA, Enterprise 6, APT, DuckDB, Parquet]
compatible: [ClawPilot, Claude Code, Cursor, GitHub Copilot]
---

# /azure-price — Azure EA Price List query skill

Fast SQL queries over the Microsoft EA (Enterprise 6) Azure Price List, sourced live from APT (Microsoft-internal Automated Price Tool) and cached as a Parquet snapshot.

## What you get

- One CLI to **submit a new price list request to APT, wait for it to generate (~15 min), download it, convert to Parquet, and cache it locally**.
- A second CLI to run sub-second SQL queries (DuckDB) over the cached snapshot — 1M+ rows, 18 columns.
- A complete API reference for APT (`/api/Pricelist/*`, `/api/Setup/GetChannels`) so you can extend it to other regions / channels / programs.
- An optional monthly automation recipe so the snapshot refreshes itself.

## Prerequisites

1. **Microsoft corporate AAD account** with access to APT (`https://aptool.azurefd.net`). The download script signs you in interactively the first time, then caches the session in a Playwright profile.
2. **Python 3.9+** with: `pip install duckdb pandas pyarrow openpyxl playwright requests` and `playwright install chromium`.
3. *(Optional, for shared storage)* an **Azure Blob container** if you want to share the snapshot across multiple machines or skills. For solo use, the local Parquet cache is enough.

## Configuration

The scripts read these environment variables (all optional):

| Variable | Default | Purpose |
|---|---|---|
| `AZURE_PRICE_DATA_DIR` | `~/.copilot/data` | Where the local Parquet cache + Playwright profile live |
| `AZURE_PRICE_STORAGE_ACCOUNT` | _(unset → local-only mode)_ | Storage account name for shared blob cache |
| `AZURE_PRICE_CONTAINER` | `azure-pricelist` | Blob container name |
| `AZURE_PRICE_BLOB` | _(latest cached file)_ | Specific blob name to download |
| `AZ_BIN` | `az` | Path to Azure CLI binary |

Add to your shell profile if you're using shared blob storage:

```bash
export AZURE_PRICE_STORAGE_ACCOUNT="<your-storage-account>"
export AZURE_PRICE_CONTAINER="azure-pricelist"
```

## Schema (DuckDB view `prices`)

| column | type |
|---|---|
| PartNumber | VARCHAR |
| ItemName | VARCHAR |
| ProductFamily | VARCHAR |
| ProductType | VARCHAR |
| Pool | VARCHAR |
| ClientLimit | VARCHAR |
| EndItemOffering | VARCHAR |
| NameDifferentiator | VARCHAR |
| Program | VARCHAR |
| Offering | VARCHAR |
| Level | VARCHAR |
| PurchaseUnit | VARCHAR |
| PurchasePeriod | VARCHAR |
| LeadD2P | VARCHAR |
| StartDate | TIMESTAMP |
| EndDate | TIMESTAMP |
| NetPrice | DOUBLE |
| ERP | DOUBLE |

## How to use (agent playbook)

When the user asks an Azure pricing question (SKUs, families, reservations, prices, overages…):

1. **Always query via DuckDB** — never load the Parquet into context, never read the xlsx directly.
2. Run:
   ```bash
   python3 ~/.copilot/skills/azure-price/query.py --sql "<SQL>" --format table
   ```
   The view is `prices`. All 18 columns above are available.
3. Schema/debug: `--schema`, `--stats`. Force re-download from blob: `--refresh`.

## Refreshing the snapshot

### Option A — Fully automated (recommended)

Submit a new APT generation, wait for completion, download + cache:

```bash
# Current month, full pipeline
python3 ~/.copilot/skills/azure-price/download_e6.py --request $(date +%Y-%m) --wait

# A specific month
python3 ~/.copilot/skills/azure-price/download_e6.py --request 2026-05 --wait
```

What happens:
- `--request YYYY-MM` POSTs to `Pricelist/Export/PricelistExcel` with sensible defaults (E6 / US / Corporate / Direct-To-End-User / Price Level A / Azure Only). Override with `--region`, `--license`, `--channel`, `--price-level`, `--sku-type`.
- `--wait` polls `PricelistFile` every 30s (override: `--poll-interval`, `--poll-timeout`, default 1800s) until the matching row is `Completed`, then downloads + chains into `refresh.py`.
- Without `--wait`, the script exits after submitting; re-run later (without `--request`) to download once it completes.

### Option B — Just download whatever's already Completed

```bash
python3 ~/.copilot/skills/azure-price/download_e6.py
```

- Opens a browser the first time (Playwright persistent profile in `$AZURE_PRICE_DATA_DIR/playwright-apt`); subsequent runs reuse cached cookies.
- Reads the MSAL token directly from the SPA, calls APT's API, downloads the latest Completed Enterprise 6 / US / Corporate / Direct-To-End-User / Azure Only file, then runs `refresh.py`.
- Useful flags: `--list` (show available files), `--no-refresh` (download only), `--token <jwt>` (skip browser; pass an APT access token directly).

### Option C — Manual ingest of an existing xlsx

```bash
python3 ~/.copilot/skills/azure-price/refresh.py "<path-to-new.xlsx>"
```

### Option D — Schedule a monthly auto-refresh

Add this to your agent's automation system, or run via cron / Task Scheduler:

```bash
# Monthly on the 1st at 09:00, refresh current month
0 9 1 * * python3 ~/.copilot/skills/azure-price/download_e6.py --request $(date +%Y-%m) --wait --poll-timeout 3600
```

The cached browser profile keeps the session alive between runs; you only need to re-auth interactively when the corporate token policy expires it.

## APT API reference (internal)

- **Base**: `https://apetool-westeurope-api.azurewebsites.net/api`
- **Token audience**: `api://c7b58982-87ea-4dc1-aa93-99eb10960d82`, scope `prod.ape.user`
- **SPA client id**: `8f90dcb9-9d41-4dfa-97ef-47df088dbbe2`
- `GET /Pricelist/PricelistFile` — list past requests for the current user
- `GET /Pricelist/Export/PricelistByFileName/{fileName}.xlsx` — download an xlsx
- `POST /Pricelist/Export/PricelistExcel` — submit a new generation request. Body:
  ```json
  {
    "programType": "E6", "programName": "Enterprise 6",
    "date": "2026-05-01T00:00:00",
    "country": "US", "countryName": "United States",
    "license": "CRP", "licenseName": "Corporate",
    "currency": "USD", "currencyName": "US Dollar",
    "priceLevel": ["A"],
    "pfNames": "", "exactMatch": true,
    "skuType": 2,
    "channel": "USR", "channelName": "Direct To End User"
  }
  ```
  `skuType`: `0`=All, `1`=All except Azure, `2`=Azure Only. Status flips InProgress → Completed in ~15 min server-side.
- `POST /Setup/GetChannels` — body `{license, country, date, programType, currency}` → `[{name, code}]`. Channel codes: `USR`=Direct To End User, `RSL`=Direct To Reseller. Some regions (Japan, Israel) only offer `RSL`.

Country codes seen so far: `US`, `GB` (UK), `ISE` (Israel-EOC), `JAP`, `EUR` (Eurozone). License: `CRP` (Corporate). Program: `E6`.

## Query cookbook

```sql
-- Find a product by name fragment
SELECT PartNumber, ItemName, NetPrice, PurchaseUnit
FROM prices
WHERE ItemName ILIKE '%app service%standard%'
  AND EndDate > CURRENT_DATE
ORDER BY NetPrice;

-- Unique ProductFamily list
SELECT DISTINCT ProductFamily FROM prices ORDER BY 1;

-- Currently-effective prices only
SELECT * FROM prices
WHERE StartDate <= CURRENT_DATE AND EndDate > CURRENT_DATE
LIMIT 20;

-- Reserved vs. pay-go comparison for a family
SELECT PurchasePeriod, COUNT(*), AVG(NetPrice)
FROM prices
WHERE ProductFamily = 'Azure Virtual Machines'
GROUP BY 1;
```

## Notes & caveats

- The xlsx is truncated at ~1.048M rows (Excel hard limit). The full EA catalog is ~1.19M rows; if full coverage is required, export per-program slices and run `refresh.py` on each.
- Blob access uses AAD (`--auth-mode login`) via your `az login` — no storage keys in the skill.
- The local cache is a plain Parquet at `$AZURE_PRICE_DATA_DIR/azure_pricelist_current.parquet`. Delete it to force a fresh download.
- **Token-via-bash gotcha**: when passing `--token` from the shell, write the JWT to a file first (`--token "$(cat /tmp/apt_token.txt)"`); inline heredocs can corrupt the dot-separated segments.
