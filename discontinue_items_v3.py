#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils"
# ]
# ///

from t3api_utils.api.operations import send_api_request
from t3api_utils.api.parallel import load_all_data_sync
from t3api_utils.main.utils import (get_authenticated_client_or_error,
                                    match_collection_from_csv, pick_license)


def main():
    # Get an authenticated client. User can choose between:
    # - Credentials (username/password)
    # - JWT token (accessible from T3 Chrome extension)
    # - API key
    api_client = get_authenticated_client_or_error()

    # Pick a license interactively
    license = pick_license(api_client=api_client)

    # Load all the items for the selected license
    all_items = load_all_data_sync(
        client=api_client,
        path="/v2/items",
        license_number=license["licenseNumber"],
    )

    # To only select the items we want to discontinue,
    # we're going to pass a CSV. 
    # 
    # Each column header must be an item property (e.g. "name")
    #
    # The simplest strategy is to pass a single-column
    # CSV that specifices the item name exactly:
    #
    #   name
    #   OG Kush 1g Prerolls
    #   Pineapple Express 1g Prerolls
    #
    # t3api_utils will look for .csv files in the same
    # folder as the running script, or you can pass
    # the path to the script manually
    filtered_items = match_collection_from_csv(
        data=all_items, on_no_match="error"
    )

    # This will discontinue the items one by one
    for item in filtered_items:
        send_api_request(
            client=api_client,
            path="/v2/items/discontinue",
            method="POST",
            params={
                "licenseNumber": license["licenseNumber"],
                "submit": True
            },
            json_body={
                "id": item["id"]
            }
        )
        


if __name__ == "__main__":
    main()
