import argparse
import csv
import datetime
import getpass
import logging
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    print("The 'requests' library is not installed.\n")
    print("To install it, run the following command:\n")
    print("    pip3 install requests\n")
    print(
        "If you are using a virtual environment, make sure it is activated before running the command."
    )
    sys.exit(1)

# Constants
BASE_URL = "https://api.trackandtrace.tools"
PAGE_SIZE = 500  # Adjustable page size based on API limits
MAX_RETRIES = 5  # Maximum number of retry attempts
RETRY_DELAY = 5  # Delay in seconds between retries
MAX_WORKERS = 5  # Number of threads to use for parallel requests
TIMEOUT_S = 20
HISTORY_BATCH_SIZE = 25  # Number of history requests to run in parallel

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Credentials:
    hostname: str
    username: str
    password: str
    otp: Optional[str] = None


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Discontinue items from CSV"
        "This script authenticates with the provided credentials and discontinues a list of items in discontinue_items.csv."
    )
    parser.add_argument(
        "--hostname",
        required=True,
        help="The hostname of the Track and Trace Tools API (e.g., mo.metrc.com). Example: --hostname=mo.metrc.com",
    )
    parser.add_argument(
        "--username",
        required=True,
        help="Username for authentication with the Track and Trace Tools API. Example: --username=user@example.com",
    )

    return parser.parse_args()


def flatten_dict(*, d: Dict, parent_key: str = "", sep: str = ".") -> Dict:
    """
    Flatten a nested dictionary.
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(d=v, parent_key=new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def make_request_with_retries(
    *,
    session: requests.Session,
    url: str,
    headers: Dict,
    params: Dict,
    max_retries: int = MAX_RETRIES,
    retry_delay: int = RETRY_DELAY,
) -> Dict:
    """
    Makes an HTTP GET request with a retry strategy.
    """
    retries = 0
    while retries < max_retries:
        try:
            response = session.get(
                url=url, headers=headers, params=params, timeout=TIMEOUT_S
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error("Request timed out. Retrying...")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e.response.status_code}, {e.response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred during the request: {str(e)}")

        retries += 1
        logger.info(f"Retrying ({retries}/{max_retries}) in {retry_delay} seconds...")
        time.sleep(retry_delay)

    raise Exception(f"Failed to complete request after {max_retries} retries.")


def fetch_page(
    *,
    session: requests.Session,
    page: int,
    headers: Dict,
    license_number: str,
) -> Dict:
    """
    Fetch a single page of items.
    """
    logger.info(f"Fetching page {page}...")
    url = f"{BASE_URL}/v2/items"
    params = {
        "licenseNumber": license_number,
        "page": page,
        "pageSize": PAGE_SIZE,
    }
    return make_request_with_retries(
        session=session, url=url, headers=headers, params=params
    )


def load_items(
    *,
    session: requests.Session,
    headers: Dict,
    license_number: str,
):
    """
    Generate a CSV report of inactive packages for a given license number.
    """
    page = 1
    total_loaded = 0
    items = []

    count_response = make_request_with_retries(
        session=session,
        url=f"{BASE_URL}/v2/items",
        headers=headers,
        params={
            "licenseNumber": license_number,
            "page": 1,
            "pageSize": 5,
        },
    )

    max_pages = math.ceil(int(count_response["total"]) / PAGE_SIZE)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_page = {
            executor.submit(
                fetch_page,
                session=session,
                page=page,
                headers=headers,
                license_number=license_number,
            ): page
            for page in range(1, max_pages + 1)
        }

        for future in as_completed(future_to_page):
            page = future_to_page[future]
            try:
                response_payload = future.result()
                if response_payload and response_payload.get("data"):
                    items.extend(response_payload["data"])
                    total_loaded += len(response_payload["data"])
                    logger.info(
                        f"Loaded {len(response_payload['data'])} items from page {page}, total loaded so far: {total_loaded}"
                    )
                else:
                    logger.info(f"No data returned for page {page}.")
            except Exception as e:
                logger.error(f"Failed to fetch page {page}: {str(e)}")

    return items


def obtain_access_token(
    *, session: requests.Session, credentials: Credentials
) -> Optional[str]:
    """
    Obtain access token using provided credentials.
    """
    logger.info("Obtaining access token...")
    url = f"{BASE_URL}/v2/auth/credentials"
    data = {
        "hostname": credentials.hostname,
        "username": credentials.username,
        "password": credentials.password,
    }
    if credentials.otp:
        data["otp"] = credentials.otp

    response = session.post(url=url, json=data, timeout=10)
    response.raise_for_status()
    access_token = response.json().get("accessToken")

    if not access_token:
        logger.error(
            "Failed to obtain access token. Please check your credentials and try again."
        )
        return None
    return access_token


def retrieve_licenses(*, session: requests.Session, headers: Dict) -> List[Dict]:
    """
    Retrieve available licenses.
    """
    logger.info("Retrieving licenses...")
    url = f"{BASE_URL}/v2/licenses"
    response = session.get(url=url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def select_license(*, licenses: List[Dict]) -> Optional[Dict]:
    """
    Allow the user to select a license from the available options.
    """
    print("Available Licenses:")
    for idx, license in enumerate(licenses):
        print(f"{idx + 1}. {license['licenseNumber']} - {license['licenseName']}")

    try:
        selected_index = int(input("Select a license by number: ")) - 1
        if 0 <= selected_index < len(licenses):
            selected_license = licenses[selected_index]
            print(f"Selected License: {selected_license['licenseName']}")
            return selected_license
        else:
            logger.error("Invalid license selection.")
    except ValueError:
        logger.error("Invalid input. Please enter a number.")
    return None



def load_item_names(*, access_token: str, current_license: dict):
    """
    Load item names
    """
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discontinue_items.csv")

    item_names = []

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


def main():
    """
    Main function to run the script.
    """
    args = parse_arguments()
    hostname = args.hostname
    username = args.username
    load_history = args.history
    password = getpass.getpass(prompt=f"Password for {hostname}/{username}: ")

    otp = None
    if hostname == "mi.metrc.com":
        otp = getpass.getpass(prompt="OTP: ")

    credentials = Credentials(
        hostname=hostname, username=username, password=password, otp=otp
    )

    with requests.Session() as session:
        try:
            access_token = obtain_access_token(session=session, credentials=credentials)
            if not access_token:
                return

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            licenses = retrieve_licenses(session=session, headers=headers)
            if not licenses:
                logger.info("No licenses found.")
                return

            current_license = select_license(licenses=licenses)
            if not current_license:
                return

            items = load_items(
                session=session,
                headers=headers,
                license_number=current_license["licenseNumber"],
            )
            
            
        except requests.exceptions.Timeout:
            logger.error(
                "Request timed out. Please check your internet connection and try again."
            )
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e.response.status_code}, {e.response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred during the request: {str(e)}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {str(e)}")


if __name__ == "__main__":
    main()
