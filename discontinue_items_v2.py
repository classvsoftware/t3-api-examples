# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "requests"
# ]
# ///

import argparse
import csv
import getpass
import logging
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

# Constants
BASE_URL = "https://api.trackandtrace.tools"
PAGE_SIZE = 500  # Adjustable page size based on API limits
MAX_RETRIES = 5  # Maximum number of retry attempts
RETRY_DELAY = 5  # Delay in seconds between retries
MAX_WORKERS = 5  # Number of threads to use for parallel requests
TIMEOUT_S = 20
SUBMIT = "true"

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
        "This script authenticates with the provided credentials and discontinues a list of items provided in a csv."
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
    parser.add_argument(
        "--csv_path",
        default="discontinue_items.csv",
        help="Path to the input CSV file containing items to discontinue. Defaults to 'discontinue_items.csv'. Example: --csv_path=path/to/file.csv",
    )

    return parser.parse_args()


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



def load_item_names_from_csv(*, csv_path: str) -> List[str]:
    """
    Load item names from the first column of a csv file
    """
    item_names: List[str] = []

    try:
        with open(csv_path, mode="r", newline="") as file:
            csv_reader = csv.reader(file)
            for row in csv_reader:
                if not row:  # Ensure the row is not empty
                    continue
                item_names.append(row[0])
    except FileNotFoundError:
        logger.error(f"The file '{csv_path}' was not found. Please ensure the file exists in the script directory.")
        raise
    except Exception as e:
        logger.error(f"An error occurred while processing the CSV file: {e}")
        raise
        
    return item_names


def discontinue_item(*, item_id: str, current_license: dict, headers: dict):
    """
    Discontinue an item.
    """
    url = f"{BASE_URL}/v2/items/discontinue"
    params = {"licenseNumber": current_license["licenseNumber"], "submit": SUBMIT}
    response = requests.post(url=url, headers=headers, params=params, json={"id": int(item_id)})
    response.raise_for_status()
    logger.info(f"Discontinued item {item_id}")



def main():
    """
    Main function to run the script.
    """
    args = parse_arguments()
    hostname = args.hostname
    username = args.username
    csv_path = args.csv_path

    item_names = load_item_names_from_csv(csv_path=csv_path)
    
    print(item_names)
    
    
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
            
            for item_name in item_names:
                item = next((item for item in items if item['name'] == item_name), None)
                
                if item is None:
                    logger.error(f"Failed to match item with name {item_name}")
                    continue
                    
                discontinue_item(item_id=item["id"], current_license=current_license, headers=headers)
            
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
