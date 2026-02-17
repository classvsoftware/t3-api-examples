#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils>=1.4.0",
# ]
# ///

# Usage:    uv run upload-item-image.py
#
# This script uploads a small test image to the T3 API.
#
# The endpoint accepts an image file via multipart/form-data and returns
# an imageFileId that can later be associated with an item.
#
# The script will:
#   1. Authenticate you with the T3 API
#   2. Let you pick a license to work under
#   3. Generate a tiny 1x1 pixel PNG test image in memory
#   4. Upload it to POST /v2/items/images/file

from t3api_utils.main.utils import (get_authenticated_client_or_error,
                                    pick_license, send_api_request)

# A minimal valid 1x1 pixel red PNG file (67 bytes).
# This avoids needing Pillow or any image library as a dependency.
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n"  # PNG signature
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde"  # IHDR chunk: 1x1, 8-bit RGB
    b"\x00\x00\x00\x0cIDATx"
    b"\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4"  # IDAT chunk
    b"\x00\x00\x00\x00IEND\xaeB`\x82"  # IEND chunk
)


def main():
    # -----------------------------------------------------------------------
    # Step 1: Authenticate
    # -----------------------------------------------------------------------
    api_client = get_authenticated_client_or_error()

    # -----------------------------------------------------------------------
    # Step 2: Pick a license
    # -----------------------------------------------------------------------
    license = pick_license(api_client=api_client)

    # -----------------------------------------------------------------------
    # Step 3: Upload the test image
    # -----------------------------------------------------------------------
    print("Uploading 1x1 test PNG image...")

    data = send_api_request(
        api_client,
        "/v2/items/images/file",
        method="POST",
        params={
            "licenseNumber": license["licenseNumber"],
            "fileType": "ItemProductImage",
            "submit": True,
        },
        files={
            "file": ("test.png", TINY_PNG, "image/png"),
        },
        expected_status=201,
    )

    print(f"Upload successful! imageFileId: {data['imageFileId']}")


if __name__ == "__main__":
    main()
