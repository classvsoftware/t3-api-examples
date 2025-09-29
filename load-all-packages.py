#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils",
# ]
# ///


from t3api_utils.api.parallel import load_all_data_sync
from t3api_utils.main.utils import (get_authenticated_client_or_error,
                                    interactive_collection_handler,
                                    pick_license)


def main():
    api_client = get_authenticated_client_or_error()
    
    license = pick_license(api_client=api_client)

    all_packages = load_all_data_sync(
        client=api_client,
        path="/v2/packages/active",
        license_number=license["licenseNumber"],
    )
    
    interactive_collection_handler(data=all_packages)

if __name__ == "__main__":
    main()
