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
BATCH_SIZE = 25  # Number of requests to run in parallel

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
        description="Export active Packages to a CSV file from Track and Trace Tools. "
        "This script authenticates with the provided credentials, fetches active packages, "
        "and optionally loads historical data for each package."
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
    start_packaged_date: str,
) -> Dict:
    """
    Fetch a single page of active packages.
    """
    logger.info(f"Fetching page {page}...")
    url = f"{BASE_URL}/v2/packages/active"
    params = {
        "licenseNumber": license_number,
        "page": page,
        "pageSize": PAGE_SIZE,
        "filter": f"packagedDate__gte:{start_packaged_date}",
    }
    return make_request_with_retries(
        session=session, url=url, headers=headers, params=params
    )


def fetch_package_labresults(
    *, session: requests.Session, package_id: str, license_number: str, headers: Dict
) -> Dict:
    """
    Fetch the history for a given package.
    """
    logger.info(f"Fetching history for package ID {package_id}...")
    url = f"{BASE_URL}/v2/packages/history"
    params = {
        "packageId": package_id,
        "licenseNumber": license_number,
    }
    return make_request_with_retries(
        session=session, url=url, headers=headers, params=params
    )


def extract_initial_package_quantity_and_unit_or_null(
    *, description: str
) -> Optional[tuple]:
    """
    Extracts the initial package quantity and unit of measure from the description.
    """
    quantity_unit_matcher = re.match(
        r"^Packaged ([0-9,.]+) ([a-zA-Z\s]+) of", description
    )
    if quantity_unit_matcher:
        return float(
            quantity_unit_matcher.group(1).replace(",", "")
        ), quantity_unit_matcher.group(2)

    plant_match = re.match(r"^Packaged ([0-9,.]+) plant", description)
    if plant_match:
        return float(plant_match.group(1).replace(",", "")), "Each"

    repackaged_plant_match = re.match(r"^Repackaged ([0-9,.]+) plant", description)
    if repackaged_plant_match:
        return float(repackaged_plant_match.group(1).replace(",", "")), "Each"

    return None


def generate_report(
    *,
    session: requests.Session,
    headers: Dict,
    license_number: str,
    start_packaged_date: str,
):
    """
    Generate a CSV report of active packages for a given license number.
    """
    page = 1
    total_loaded = 0
    packages = []

    count_response = make_request_with_retries(
        session=session,
        url=f"{BASE_URL}/v2/packages/active",
        headers=headers,
        params={
            "licenseNumber": license_number,
            "page": 1,
            "pageSize": 5,
            "filter": f"packagedDate__gte:{start_packaged_date}",
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
                start_packaged_date=start_packaged_date,
            ): page
            for page in range(1, max_pages + 1)
        }

        for future in as_completed(future_to_page):
            page = future_to_page[future]
            try:
                response_payload = future.result()
                if response_payload and response_payload.get("data"):
                    packages.extend(response_payload["data"])
                    total_loaded += len(response_payload["data"])
                    logger.info(
                        f"Loaded {len(response_payload['data'])} packages from page {page}, total loaded so far: {total_loaded}"
                    )
                else:
                    logger.info(f"No data returned for page {page}.")
            except Exception as e:
                logger.error(f"Failed to fetch page {page}: {str(e)}")

    fetch_package_lab_results(
        session=session,
        packages=packages,
        headers=headers,
        license_number=license_number,
    )

    packages = [flatten_dict(d=x) for x in packages]
    write_to_csv(packages=packages, license_number=license_number)


def fetch_package_lab_results(
    *,
    session: requests.Session,
    packages: List[Dict],
    headers: Dict,
    license_number: str,
):
    """
    Fetch history for each package in batches.
    """
    total_packages = len(packages)
    for i in range(0, total_packages, BATCH_SIZE):
        batch = packages[i : i + BATCH_SIZE]
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_package = {
                executor.submit(
                    fetch_package_labresults,
                    session=session,
                    package_id=pkg["id"],
                    license_number=license_number,
                    headers=headers,
                ): pkg
                for pkg in batch
            }

            for future in as_completed(future_to_package):
                package = future_to_package[future]
                try:
                    labresults_response = future.result()
                    if labresults_response:
                        package["_labresults"] = labresults_response.get("data")
                        logger.info(
                            f"Lab results attached for package ID {package['id']}"
                        )
                    else:
                        logger.info(
                            f"No lab results returned for package ID {package['id']}"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to fetch lab results for package ID {package['id']}: {str(e)}"
                    )


def write_to_csv(*, packages: List[Dict], license_number: str):
    """
    Write the packages data to a CSV file.
    """
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    csv_path = os.path.join(
        output_dir,
        f'{license_number}_active_packages_lab_results{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.csv',
    )

    if packages:
        # Flatten packages into lab results

        lab_results = []

        for pkg in packages:
            lab_results.extend(
                [
                    {
                        **{"labresult." + k: v for k, v in lab_result.items()},
                        **{k: v for k, v in pkg.items() if k != "_labresults"},
                    }
                    for lab_result in pkg["_labresults"]
                ]
            )

        fieldnames = list({key for lab_result in lab_results for key in lab_result})

        # Define the desired order
        priority_order = ["label", "item.name", "quantity", "unitOfMeasureAbbreviation"]

        # Sort the fieldnames
        ordered_fieldnames = sorted(
            fieldnames,
            key=lambda x: (
                priority_order.index(x)
                if x in priority_order
                else (
                    len(priority_order)
                    if x.startswith("labresult.")
                    else len(priority_order) + 1
                )
            ),
        )

        try:
            with open(csv_path, mode="w", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=ordered_fieldnames)
                writer.writeheader()
                writer.writerows(lab_results)
            logger.info(f"Report generated: {csv_path}")
        except IOError as e:
            logger.error(f"Failed to write CSV file: {str(e)}")
    else:
        logger.info("No active packages found for the selected license.")


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

            start_packaged_date = input("Enter the start package date (YYYY-MM-DD): ")
            generate_report(
                session=session,
                headers=headers,
                license_number=current_license["licenseNumber"],
                start_packaged_date=start_packaged_date,
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
