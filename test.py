#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils",
# ]
# ///


from t3api_utils.main.utils import get_authenticated_client_or_error


def main():
    get_authenticated_client_or_error()

if __name__ == "__main__":
    main()
