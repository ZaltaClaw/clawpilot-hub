#!/usr/bin/env python3
"""Azure Price List query tool — DuckDB over local Parquet cache.

Usage:
    python3 query.py --sql "SELECT * FROM prices WHERE ProductFamily='Azure App Service' LIMIT 10"
    python3 query.py --schema
    python3 query.py --refresh     # re-download latest parquet from blob (if configured)
    python3 query.py --stats

The Parquet file is cached locally at $AZURE_PRICE_DATA_DIR/azure_pricelist_current.parquet
(default: ~/.copilot/data/azure_pricelist_current.parquet). If a shared Azure Blob is
configured via env vars, the first run (or --refresh) downloads it; otherwise the cache
must be populated by download_e6.py or refresh.py.

Environment variables (all optional):
    AZURE_PRICE_DATA_DIR        Where the local cache lives (default: ~/.copilot/data)
    AZURE_PRICE_STORAGE_ACCOUNT Storage account for shared blob cache (unset = local-only)
    AZURE_PRICE_CONTAINER       Blob container (default: azure-pricelist)
    AZURE_PRICE_BLOB            Specific blob to download (default: azure_pricelist_current.parquet)
    AZ_BIN                      Path to az CLI (default: az)
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import duckdb

DATA_DIR = Path(os.environ.get("AZURE_PRICE_DATA_DIR", str(Path.home() / ".copilot" / "data"))).expanduser()
CACHE = DATA_DIR / "azure_pricelist_current.parquet"
META = DATA_DIR / "azure_pricelist_current.json"

STORAGE_ACCOUNT = os.environ.get("AZURE_PRICE_STORAGE_ACCOUNT", "")
CONTAINER = os.environ.get("AZURE_PRICE_CONTAINER", "azure-pricelist")
BLOB_NAME = os.environ.get("AZURE_PRICE_BLOB", "azure_pricelist_current.parquet")
AZ = os.environ.get("AZ_BIN", "az")


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def download(force: bool = False) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE.exists() and not force:
        return CACHE
    if not STORAGE_ACCOUNT:
        raise SystemExit(
            f"No cached Parquet at {CACHE} and AZURE_PRICE_STORAGE_ACCOUNT is unset. "
            "Run download_e6.py to fetch a fresh snapshot from APT, or set the env var "
            "to download from a shared Azure Blob container."
        )
    print(f"Downloading {BLOB_NAME} from {STORAGE_ACCOUNT}/{CONTAINER}...", file=sys.stderr)
    _run([
        AZ, "storage", "blob", "download",
        "--account-name", STORAGE_ACCOUNT,
        "--container-name", CONTAINER,
        "--name", BLOB_NAME,
        "--file", str(CACHE),
        "--auth-mode", "login",
        "--overwrite",
        "-o", "none",
    ])
    META.write_text(json.dumps({"blob": BLOB_NAME, "account": STORAGE_ACCOUNT}))
    return CACHE


def connect() -> duckdb.DuckDBPyConnection:
    path = download(force=False)
    con = duckdb.connect()
    con.execute(f"CREATE OR REPLACE VIEW prices AS SELECT * FROM read_parquet('{path}')")
    return con


def cmd_schema():
    con = connect()
    rows = con.execute("DESCRIBE prices").fetchall()
    print(f"Table: prices  ({con.execute('SELECT COUNT(*) FROM prices').fetchone()[0]:,} rows)")
    print(f"{'column':<22} {'type':<15} nullable")
    for r in rows:
        print(f"{r[0]:<22} {str(r[1]):<15} {r[2]}")


def cmd_stats():
    con = connect()
    n = con.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    fams = con.execute(
        "SELECT ProductFamily, COUNT(*) c FROM prices GROUP BY 1 ORDER BY c DESC LIMIT 20"
    ).fetchall()
    print(f"Total rows: {n:,}\nTop ProductFamily values:")
    for f, c in fams:
        print(f"  {c:>8,}  {f}")


def cmd_sql(sql: str, fmt: str = "table"):
    con = connect()
    res = con.execute(sql)
    if fmt == "json":
        cols = [d[0] for d in res.description]
        rows = [dict(zip(cols, r)) for r in res.fetchall()]
        print(json.dumps(rows, default=str, indent=2))
    elif fmt == "csv":
        import csv
        w = csv.writer(sys.stdout)
        w.writerow([d[0] for d in res.description])
        for r in res.fetchall():
            w.writerow(r)
    else:
        df = res.fetch_df()
        with_opts = {"display.max_columns": None, "display.width": 200, "display.max_colwidth": 60}
        import pandas as pd
        with pd.option_context(*[v for kv in with_opts.items() for v in kv]):
            print(df.to_string(index=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sql", help="SQL to execute against view `prices`")
    p.add_argument("--schema", action="store_true", help="show columns & row count")
    p.add_argument("--stats", action="store_true", help="show ProductFamily distribution")
    p.add_argument("--refresh", action="store_true", help="re-download parquet from Azure blob")
    p.add_argument("--format", choices=["table", "json", "csv"], default="table")
    args = p.parse_args()

    if args.refresh:
        download(force=True)
        print("Refreshed.")
        return
    if args.schema:
        cmd_schema(); return
    if args.stats:
        cmd_stats(); return
    if args.sql:
        cmd_sql(args.sql, args.format); return
    p.print_help()


if __name__ == "__main__":
    main()
