#!/usr/bin/env python3
"""Download the latest Enterprise 6 (Azure Only) price list xlsx from APT.

APT = Microsoft-internal WCF Automated Price Tool at https://aptool.azurefd.net/

Auth: opens a Playwright browser (visible). Reuses the persistent profile in
``~/.copilot/data/playwright-apt`` so sign-in is needed only the first time
(plus the periodic Microsoft re-auth).

What it does:
  1. Open APT and read the MSAL access token cached by the SPA
     (audience ``api://c7b58982-87ea-4dc1-aa93-99eb10960d82``,
     scope ``prod.ape.user``).
  2. Call the API directly to list completed Azure-only E6 / United States /
     Corporate / Direct To End User pricelist files for the current user.
  3. Download the most recent Completed file (xlsx) to a temp path.
  4. Optionally chain into refresh.py to convert -> Parquet and upload to Blob.

Usage:
    python3 download_e6.py                 # download + refresh
    python3 download_e6.py --no-refresh    # download only, print path
    python3 download_e6.py --out PATH      # custom destination
    python3 download_e6.py --headed        # visible browser (default)
    python3 download_e6.py --headless      # headless (will fail if MFA needed)

Filtering (defaults match the user's normal monthly download):
    --program "Enterprise 6"
    --region "United States"
    --license "Corporate"
    --channel "Direct To End User"
    --price-level "A"
    --sku-type 2          (2 = Azure Only)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

APT_URL = "https://aptool.azurefd.net/search/price/pricelist-download"
API_BASE = "https://apetool-westeurope-api.azurewebsites.net/api"
API_AUDIENCE = "api://c7b58982-87ea-4dc1-aa93-99eb10960d82"

import os
_DATA_DIR_DEFAULT = Path.home() / ".copilot" / "data"
DATA_DIR = Path(os.environ.get("AZURE_PRICE_DATA_DIR", str(_DATA_DIR_DEFAULT))).expanduser()
PROFILE_DIR = DATA_DIR / "playwright-apt"


def acquire_token(headed: bool = True, timeout_s: int = 300) -> str:
    """Open APT, wait for MSAL cache to contain an APE access token, return it."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=not headed,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(APT_URL, wait_until="domcontentloaded", timeout=120_000)
        except Exception as e:
            print(f"navigation: {e}", file=sys.stderr)

        deadline = time.time() + timeout_s
        token = None
        while time.time() < deadline:
            token = page.evaluate(
                """() => {
                    for (const storage of [localStorage, sessionStorage]) {
                        for (let i = 0; i < storage.length; i++) {
                            const k = storage.key(i);
                            if (k.includes('accesstoken') && k.includes('c7b58982')) {
                                try { return JSON.parse(storage.getItem(k)).secret; } catch(e) {}
                            }
                        }
                    }
                    return null;
                }"""
            )
            if token:
                break
            print("Waiting for sign-in (complete it in the browser)...", file=sys.stderr)
            time.sleep(3)
        ctx.close()
        if not token:
            raise RuntimeError("Timed out waiting for APT access token")
        return token


def list_pricelists(token: str) -> list[dict]:
    r = requests.get(
        f"{API_BASE}/Pricelist/PricelistFile",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


# Country/license/channel codes captured from APT.
# Extend if you ever submit non-default combos.
COUNTRY_CODES = {
    "United States": ("US", "USD", "US Dollar"),
    "United Kingdom": ("GB", "GBP", "British Pound"),
    "Israel (EOC)":  ("ISE", "USD", "US Dollar"),
    "Japan":         ("JAP", "JPY", "Japanese Yen"),
    "Eurozone":      ("EU", "EUR", "Euro"),
}
LICENSE_CODES = {"Corporate": "CRP", "Government": "GOV", "Local Government": "LGV"}
CHANNEL_CODES = {"Direct To End User": "USR", "Direct To Reseller": "RSL"}
PROGRAM_CODES = {"Enterprise 6": "E6", "EA Subscription": "EAS"}


def submit_pricelist(
    token: str,
    *,
    price_date: str,           # "YYYY-MM" or "YYYY-MM-DD"
    program: str = "Enterprise 6",
    region: str = "United States",
    license_type: str = "Corporate",
    channel: str = "Direct To End User",
    price_level: str = "A",
    sku_type: int = 2,
    pfam_keyword: str = "",
    exact_match: bool = True,
) -> dict:
    """POST a new pricelist generation request to APT."""
    if len(price_date) == 7:
        price_date = f"{price_date}-01"
    iso_date = f"{price_date}T00:00:00"

    if region not in COUNTRY_CODES:
        raise ValueError(f"Unknown region {region!r}; add to COUNTRY_CODES (country/currency codes)")
    country_code, currency_code, currency_name = COUNTRY_CODES[region]
    program_code = PROGRAM_CODES.get(program, program)
    license_code = LICENSE_CODES.get(license_type, license_type)
    channel_code = CHANNEL_CODES.get(channel, channel)

    body = {
        "programType": program_code, "programName": program,
        "date": iso_date,
        "country": country_code, "countryName": region,
        "license": license_code, "licenseName": license_type,
        "currency": currency_code, "currencyName": currency_name,
        "priceLevel": [price_level],
        "pfNames": pfam_keyword, "exactMatch": exact_match,
        "skuType": sku_type,
        "channel": channel_code, "channelName": channel,
    }
    r = requests.post(
        f"{API_BASE}/Pricelist/Export/PricelistExcel",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=120,
    )
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


def wait_for_completion(
    token: str,
    *,
    price_date: str,
    program: str,
    region: str,
    license_type: str,
    channel: str,
    price_level: str,
    sku_type: int,
    poll_interval_s: int = 30,
    timeout_s: int = 1800,
) -> dict:
    """Poll PricelistFile until a matching Completed file appears."""
    if len(price_date) == 7:
        price_date = f"{price_date}-01"
    deadline = time.time() + timeout_s
    last_status = None
    while time.time() < deadline:
        files = list_pricelists(token)
        for f in files:
            if (
                f.get("program") == program
                and f.get("region") == region
                and f.get("licenseType") == license_type
                and f.get("channel") == channel
                and f.get("priceLevel") == price_level
                and f.get("skuType") == sku_type
                and f.get("date", "").startswith(price_date)
            ):
                if f.get("status") == "Completed":
                    return f
                if f.get("status") != last_status:
                    print(f"  status: {f.get('status')}", file=sys.stderr)
                    last_status = f.get("status")
                break
        time.sleep(poll_interval_s)
    raise TimeoutError(f"Pricelist for {price_date} did not complete within {timeout_s}s")


def filter_files(
    files: list[dict],
    program: str,
    region: str,
    license_type: str,
    channel: str,
    price_level: str,
    sku_type: int,
) -> list[dict]:
    matches = [
        f for f in files
        if f.get("status") == "Completed"
        and f.get("program") == program
        and f.get("region") == region
        and f.get("licenseType") == license_type
        and f.get("channel") == channel
        and f.get("priceLevel") == price_level
        and f.get("skuType") == sku_type
    ]
    matches.sort(key=lambda f: f.get("date") or "", reverse=True)
    return matches


def download_file(token: str, file_name: str, out_path: Path) -> Path:
    url = f"{API_BASE}/Pricelist/Export/PricelistByFileName/{file_name}"
    with requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
        timeout=600,
    ) as r:
        r.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--program", default="Enterprise 6")
    ap.add_argument("--region", default="United States")
    ap.add_argument("--license", dest="license_type", default="Corporate")
    ap.add_argument("--channel", default="Direct To End User")
    ap.add_argument("--price-level", default="A")
    ap.add_argument("--sku-type", type=int, default=2, help="2 = Azure Only, 0 = All, 1 = All except Azure")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--headed", action="store_true", default=True)
    ap.add_argument("--no-refresh", action="store_true", help="Skip running refresh.py after download")
    ap.add_argument("--list", action="store_true", help="List available files and exit")
    ap.add_argument("--token", help="Bearer token (skip browser auth). Useful for one-off runs.")
    ap.add_argument(
        "--request",
        metavar="YYYY-MM",
        help="Submit a new pricelist generation request for this price date (e.g. 2026-05). "
             "Combine with --wait to also poll for completion + download.",
    )
    ap.add_argument(
        "--wait",
        action="store_true",
        help="After --request, poll until the file is Completed, then download + refresh.",
    )
    ap.add_argument("--poll-interval", type=int, default=30, help="Seconds between status polls (default 30)")
    ap.add_argument("--poll-timeout", type=int, default=1800, help="Max seconds to wait (default 1800 = 30 min)")
    args = ap.parse_args()

    headed = not args.headless

    if args.token:
        token = args.token.strip()
        if token.lower().startswith("bearer "):
            token = token[7:]
    else:
        print("Acquiring APT access token...", file=sys.stderr)
        token = acquire_token(headed=headed)

    channel_name = args.channel

    if args.request:
        print(f"Submitting pricelist request for {args.request} ({args.program}/{args.region}/{channel_name})...", file=sys.stderr)
        resp = submit_pricelist(
            token,
            price_date=args.request,
            program=args.program,
            region=args.region,
            license_type=args.license_type,
            channel=channel_name,
            price_level=args.price_level,
            sku_type=args.sku_type,
        )
        print(f"  submit response: {resp}", file=sys.stderr)
        if not args.wait:
            print("Submitted. Re-run without --request (or with --wait) once the file completes (~15 min).", file=sys.stderr)
            return 0
        print(f"Polling every {args.poll_interval}s (timeout {args.poll_timeout}s)...", file=sys.stderr)
        wait_for_completion(
            token,
            price_date=args.request,
            program=args.program,
            region=args.region,
            license_type=args.license_type,
            channel=channel_name,
            price_level=args.price_level,
            sku_type=args.sku_type,
            poll_interval_s=args.poll_interval,
            timeout_s=args.poll_timeout,
        )
        print("File completed. Proceeding to download.", file=sys.stderr)

    print("Fetching pricelist file history...", file=sys.stderr)
    files = list_pricelists(token)
    matches = filter_files(
        files,
        program=args.program,
        region=args.region,
        license_type=args.license_type,
        channel=args.channel,
        price_level=args.price_level,
        sku_type=args.sku_type,
    )

    if args.list:
        for f in matches:
            print(f"{f['date'][:10]}  {f['fileName']}  rows={f['recordCount']}  finished={f.get('finishTime')}")
        return 0

    if not matches:
        print("No completed pricelist files match the filter.", file=sys.stderr)
        print("Available statuses for your queries:", file=sys.stderr)
        for f in files[:10]:
            print(f"  {f.get('status')} {f.get('date','')[:10]} {f.get('program')} {f.get('region')}", file=sys.stderr)
        return 1

    latest = matches[0]
    tag = latest["date"][:7]  # YYYY-MM
    out = args.out or DATA_DIR / f"azure_pricelist_{tag}.xlsx"

    print(f"Downloading {latest['fileName']} (price date {latest['date'][:10]}, {latest['recordCount']:,} rows) -> {out}", file=sys.stderr)
    download_file(token, latest["fileName"], out)
    size_mb = out.stat().st_size / 1e6
    print(f"Downloaded {size_mb:.1f} MB", file=sys.stderr)

    if not args.no_refresh:
        print("Running refresh.py to convert + upload Parquet...", file=sys.stderr)
        rc = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("refresh.py")), str(out)],
        ).returncode
        if rc != 0:
            print(f"refresh.py exited with {rc}", file=sys.stderr)
            return rc

    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
