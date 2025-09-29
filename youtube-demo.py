#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils",
#     "typer"
# ]
# ///


import typer
from t3api_utils.api.operations import send_api_request
from t3api_utils.api.parallel import load_all_data_sync
from t3api_utils.main.utils import (get_authenticated_client_or_error,
                                    interactive_collection_handler,
                                    match_collection_from_csv, pick_license)


def main():
    api_client = get_authenticated_client_or_error()

    license = pick_license(api_client=api_client)

    all_items = load_all_data_sync(
        client=api_client,
        path="/v2/items",
        license_number=license["licenseNumber"],
    )

    interactive_collection_handler(data=all_items)

    filtered_items = match_collection_from_csv(data=all_items, on_no_match="error")

    if not typer.confirm(
        f"You're about to discontinue {len(filtered_items)} items, continue?"
    ):
        raise typer.Exit(code=1)

    for item in filtered_items:
        send_api_request(
            client=api_client,
            path="/v2/items/discontinue",
            method="POST",
            params={"licenseNumber": license["licenseNumber"], "submit": True},
            json_body={"id": item["id"]},
        )


if __name__ == "__main__":
    main()
