import argparse
import csv
import getpass
import os
import logging
from typing import List, Optional

import requests

# Constants
BASE_URL = "https://api.trackandtrace.tools"
SUBMIT = "true"  # When ready to submit to Metrc, change this to "true"

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Process sales receipts from Track and Trace Tools."
    )
    parser.add_argument("--hostname", required=True, help="The hostname of the Track and Trace Tools API (e.g., mo.metrc.com)")
    parser.add_argument("--username", required=True, help="Username for authentication with the Track and Trace Tools API.")
    return parser.parse_args()


def obtain_access_token(*, hostname: str, username: str, password: str, otp: Optional[str] = None) -> Optional[str]:
    """
    Obtain access token using provided credentials.
    """
    logger.info("Obtaining access token...")
    url = f"{BASE_URL}/v2/auth/credentials"
    data = {"hostname": hostname, "username": username, "password": password}
    if otp:
        data["otp"] = otp

    response = requests.post(url, json=data)
    response.raise_for_status()
    access_token = response.json().get("accessToken")

    if not access_token:
        logger.error("Failed to obtain access token. Please check your credentials and try again.")
        return None
    return access_token


def retrieve_licenses(*, access_token: str) -> List[dict]:
    """
    Retrieve available licenses.
    """
    logger.info("Retrieving licenses...")
    url = f"{BASE_URL}/v2/licenses"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def select_license(*, licenses: List[dict]) -> Optional[dict]:
    """
    Allow the user to select a license from the available options.
    """
    print("Available Licenses:")
    for idx, license in enumerate(licenses):
        print(f"{idx + 1}. {license}")

    try:
        selected_index = int(input("Select a license by number: ")) - 1
        if 0 <= selected_index < len(licenses):
            selected_license = licenses[selected_index]
            print(f"Selected License: {selected_license}")
            return selected_license
        else:
            logger.error("Invalid license selection.")
    except ValueError:
        logger.error("Invalid input. Please enter a number.")
    return None


def process_sales_receipts(*, access_token: str, current_license: dict):
    """
    Process sales receipts from the CSV file.
    """
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sales_receipts.csv")

    try:
        with open(csv_path, mode="r", newline="") as file:
            csv_reader = csv.reader(file)
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            for row in csv_reader:
                if not row:  # Ensure the row is not empty
                    continue
                logger.info(f"Processing sales receipt {row[0]}...")
                unfinalize_receipt(receipt_id=row[0], current_license=current_license, headers=headers)
                void_receipt(receipt_id=row[0], current_license=current_license, headers=headers)
            logger.info("All receipts processed successfully.")
    except FileNotFoundError:
        logger.error("The file 'sales_receipts.csv' was not found. Please ensure the file exists in the script directory.")
    except Exception as e:
        logger.error(f"An error occurred while processing the CSV file: {e}")


def unfinalize_receipt(*, receipt_id: str, current_license: dict, headers: dict):
    """
    Unfinalize a sales receipt.
    """
    url = f"{BASE_URL}/v2/sales/unfinalize"
    params = {"licenseNumber": current_license["licenseNumber"], "submit": SUBMIT}
    response = requests.post(url=url, headers=headers, params=params, json=[{"id": int(receipt_id)}])
    response.raise_for_status()
    logger.info(f"Unfinalized sales receipt {receipt_id}")


def void_receipt(*, receipt_id: str, current_license: dict, headers: dict):
    """
    Void a sales receipt.
    """
    url = f"{BASE_URL}/v2/sales/void"
    params = {"licenseNumber": current_license["licenseNumber"], "submit": SUBMIT}
    response = requests.post(url=url, headers=headers, params=params, json={"id": int(receipt_id)})
    response.raise_for_status()
    logger.info(f"Voided sales receipt {receipt_id}")


def main():
    """
    Main function to run the script.
    """
    args = parse_arguments()
    hostname = args.hostname
    username = args.username
    password = getpass.getpass(prompt=f"Password for {hostname}/{username}: ")

    otp = None
    if hostname == "mi.metrc.com":
        otp = getpass.getpass(prompt="OTP: ")

    try:
        access_token = obtain_access_token(hostname=hostname, username=username, password=password, otp=otp)
        if not access_token:
            return

        licenses = retrieve_licenses(access_token=access_token)
        if not licenses:
            logger.info("No licenses found.")
            return

        current_license = select_license(licenses=licenses)
        if not current_license:
            return

        input("This script will now unfinalize and void all receipt numbers in sales_receipts.csv. Press enter to continue.")
        process_sales_receipts(access_token=access_token, current_license=current_license)
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {e}")
        if e.response is not None:
            logger.error(f"Response status code: {e.response.status_code}")
            logger.error(f"Response content: {e.response.text}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
