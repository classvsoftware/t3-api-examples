#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils>=1.5.0",
# ]
# ///

# Usage:    uv run download-manifest.py
#
# This script downloads a single manifest PDF from an incoming transfer.
#
# It will:
#   1. Authenticate you with the T3 API
#   2. Let you pick a license
#   3. Load all active incoming transfers
#   4. Let you select a transfer by manifest number
#   5. Download the manifest PDF to the output/ directory

import os

from t3api_utils.api.parallel import load_all_data_sync
from t3api_utils.main.utils import (get_authenticated_client_or_error,
                                    pick_license, send_api_request)


def pick_transfer(transfers):
    if not transfers:
        print("No incoming transfers found for this license.")
        raise SystemExit(1)

    print(f"\nFound {len(transfers)} incoming transfer(s):\n")
    for i, t in enumerate(transfers, 1):
        manifest = t.get("manifestNumber", "N/A")
        pkg_count = t.get("deliveryPackageCount", "?")
        shipper = t.get("shipperFacilityName", "Unknown")
        print(f"  {i}. {manifest}  |  {pkg_count} packages  |  {shipper}")

    print()
    while True:
        choice = input("Select a transfer (number): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(transfers):
                return transfers[idx]
        except ValueError:
            pass
        print("Invalid selection, try again.")


def main():
    api_client = get_authenticated_client_or_error()

    license = pick_license(api_client=api_client)
    license_number = license["licenseNumber"]

    print("\nLoading incoming transfers...")
    transfers = load_all_data_sync(
        client=api_client,
        path="/v2/transfers/incoming/active",
        license_number=license_number,
    )

    transfer = pick_transfer(transfers)
    manifest_number = transfer["manifestNumber"]

    print(f"\nDownloading manifest PDF for {manifest_number}...")

    pdf_bytes = send_api_request(
        api_client,
        "/v2/transfers/manifest",
        params={
            "licenseNumber": license_number,
            "manifestNumber": manifest_number,
        },
        response_type="bytes",
    )

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{manifest_number}.pdf")

    with open(output_path, "wb") as f:
        f.write(pdf_bytes)

    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
