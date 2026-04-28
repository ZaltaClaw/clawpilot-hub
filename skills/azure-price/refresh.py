#!/usr/bin/env python3
"""Refresh the Azure Price List Parquet cache from a newer xlsx.

Usage:
    python3 refresh.py <path-to-xlsx>

- Converts xlsx -> parquet, writes to $AZURE_PRICE_DATA_DIR/azure_pricelist_<YYYY-MM>.parquet
- Updates the local pointer azure_pricelist_current.parquet to the new file
- If AZURE_PRICE_STORAGE_ACCOUNT is set, also uploads to Azure Blob (both
  azure_pricelist_<YYYY-MM>.parquet and azure_pricelist_current.parquet)

The month tag is parsed from the xlsx filename if it matches `... YYYY-MM ...`,
otherwise falls back to today's YYYY-MM.

Environment variables (all optional):
    AZURE_PRICE_DATA_DIR        Where the local cache lives (default: ~/.copilot/data)
    AZURE_PRICE_STORAGE_ACCOUNT Storage account for shared blob cache (unset = local-only)
    AZURE_PRICE_CONTAINER       Blob container (default: azure-pricelist)
    AZ_BIN                      Path to az CLI (default: az)
"""
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.environ.get("AZURE_PRICE_DATA_DIR", str(Path.home() / ".copilot" / "data"))).expanduser()
STORAGE_ACCOUNT = os.environ.get("AZURE_PRICE_STORAGE_ACCOUNT", "")
CONTAINER = os.environ.get("AZURE_PRICE_CONTAINER", "azure-pricelist")
AZ = os.environ.get("AZ_BIN", "az")


def main():
    if len(sys.argv) != 2:
        print("usage: refresh.py <path-to-xlsx>", file=sys.stderr); sys.exit(2)
    src = Path(sys.argv[1]).expanduser()
    if not src.exists():
        print(f"file not found: {src}", file=sys.stderr); sys.exit(1)

    m = re.search(r"(\d{4}-\d{2})", src.name)
    tag = m.group(1) if m else date.today().strftime("%Y-%m")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / f"azure_pricelist_{tag}.parquet"

    print(f"Converting {src.name} -> {out.name} ...")
    df = pd.read_excel(src, sheet_name="AzurePriceList", header=2, engine="openpyxl")
    for c in ("NetPrice", "ERP"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("StartDate", "EndDate"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df.to_parquet(out, engine="pyarrow", compression="snappy", index=False)
    print(f"  {len(df):,} rows, {out.stat().st_size/1e6:.1f} MB")

    if STORAGE_ACCOUNT:
        blob_name = f"azure_pricelist_{tag}.parquet"
        for target in (blob_name, "azure_pricelist_current.parquet"):
            print(f"Uploading -> {CONTAINER}/{target}")
            subprocess.run([
                AZ, "storage", "blob", "upload",
                "--account-name", STORAGE_ACCOUNT,
                "--container-name", CONTAINER,
                "--name", target,
                "--file", str(out),
                "--auth-mode", "login",
                "--overwrite",
                "-o", "none",
            ], check=True)
    else:
        print("(AZURE_PRICE_STORAGE_ACCOUNT not set — skipping blob upload, local cache only)")

    cache = DATA_DIR / "azure_pricelist_current.parquet"
    if cache.exists() or cache.is_symlink():
        cache.unlink()
    cache.symlink_to(out)
    print(f"\nDone. Local cache -> {cache} -> {out.name}")


if __name__ == "__main__":
    main()
