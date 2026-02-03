#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils",
# ]
# ///


import json

from t3api_utils.api.operations import send_api_request
from t3api_utils.main.utils import get_authenticated_client_or_error


def main():
    api_client = get_authenticated_client_or_error()

    result = send_api_request(
        api_client,
        "/v2/auth/whoami"
    )

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
