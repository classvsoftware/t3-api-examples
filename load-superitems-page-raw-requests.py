#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils",
# ]
# ///


import os
import shutil

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
    
    data = response.json()['data']

    interactive_collection_handler(data=data)

    # Clear and recreate output/images directory
    output_dir = "output/images"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    # Download all images from metadata
    auth_headers = {"Authorization": f"Bearer {api_client.access_token}"}

    item = data[0]
    
    metadata = item.get('metadata', {})
    item_images = metadata.get('itemImages', [])

    for image in item_images:
        image_url = image.get('imageUrl')
        file_name = image.get('fileName')

        if not image_url or not file_name:
            continue

        # Use just the filename (strip any directory path in the name)
        safe_filename = os.path.basename(file_name)
        output_path = os.path.join(output_dir, file_name)

        print(f"Downloading: {safe_filename}")

        img_response = httpx.get(image_url, headers=auth_headers)

        if img_response.status_code == 200:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(img_response.content)
        else:
            print(f"  Failed to download: {img_response.status_code}")

    

if __name__ == "__main__":
    main()
