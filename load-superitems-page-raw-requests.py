#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils",
# ]
# ///


import httpx
from t3api_utils.api.operations import get_collection
from t3api_utils.api.parallel import load_all_data_sync
from t3api_utils.main.utils import (get_authenticated_client_or_error,
                                    interactive_collection_handler,
                                    pick_license)


def main():
    api_client = get_authenticated_client_or_error()
    
    license = pick_license(api_client=api_client)

    response = httpx.get(
        f"{api_client._config.host}/v2/items/super",
        headers={
            "Authorization": f"Bearer {api_client.access_token}"
        },
        params={
            "licenseNumber": license["licenseNumber"],
            "pageSize": 50,
            "include": "images"
        }   
    )
    
    print(response.json()['data'][0]['metadata'])
    
    # {'itemImages': [{'fileName': '(CUL03) Codes _ Green Bag _ Flower _ 3.5g _ [Strain]/Screenshot 2024-01-22 093354.png', 'fileType': 'ItemProductImage', 'imageFileId': 2890687, 'imageUrl': 'https://api.trackandtrace.tools/v2/items/photos?licenseNumber=CUL000003&itemId=2520568&imageFileId=2890687'}, {'fileName': '(CUL03) Codes _ Green Bag _ Flower _ 3.5g _ [Strain]/3.5g Bag Flower D9THCa label.png', 'fileType': 'ItemLabelImage', 'imageFileId': 2890688, 'imageUrl': 'https://api.trackandtrace.tools/v2/items/photos?licenseNumber=CUL000003&itemId=2520568&imageFileId=2890688'}, {'fileName': '(CUL03) Codes _ Green Bag _ Flower _ 3.5g _ [Strain]/Packaging Photo Codes Green Bag Flower 3.5g Prepack.png', 'fileType': 'ItemPackagingImage', 'imageFileId': 2890689, 'imageUrl': 'https://api.trackandtrace.tools/v2/items/photos?licenseNumber=CUL000003&itemId=2520568&imageFileId=2890689'}]}
    
    # interactive_collection_handler(data=items_page["data"])

    

if __name__ == "__main__":
    main()
    main()
