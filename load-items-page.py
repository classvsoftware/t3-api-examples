#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils",
# ]
# ///


from t3api_utils.api.operations import get_collection
from t3api_utils.main.utils import (get_authenticated_client_or_error,
                                    interactive_collection_handler,
                                    pick_license)


def main():
    api_client = get_authenticated_client_or_error()
    
    license = pick_license(api_client=api_client)

    items_page = get_collection(
        client=api_client,
        path="/v2/items",
        license_number=license["licenseNumber"],
    )
    
    interactive_collection_handler(data=items_page["data"])

if __name__ == "__main__":
    main()
