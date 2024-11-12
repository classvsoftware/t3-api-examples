import argparse
import getpass
import logging
import sys
from dataclasses import dataclass
from typing import Dict, Optional

try:
    import requests
except ImportError:
    print("The 'requests' library is not installed.\n")
    print("To install it, run the following command:\n")
    print("    pip install requests\n")
    print("If you are using a virtual environment, make sure it is activated before running the command.")
    sys.exit(1)
    
# Constants
BASE_URL = "https://api.trackandtrace.tools"
TIMEOUT_S = 20

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
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
        description="Check API access configuration for Track and Trace Tools."
    )
    parser.add_argument(
        "--hostname", 
        required=True, 
        help="The hostname of the Track and Trace Tools API (e.g., mo.metrc.com). This is required to target the correct server. "
             "Example: --hostname=mo.metrc.com"
    )
    parser.add_argument(
        "--username", 
        required=True, 
        help="Username for authentication with the Track and Trace Tools API. "
             "This should be a valid email or user identifier for the account. "
             "Example: --username=user@example.com"
    )
    return parser.parse_args()

def obtain_access_token(*, session: requests.Session, credentials: Credentials) -> Optional[str]:
    """
    Obtain access token using provided credentials.
    """
    logger.info("Obtaining access token...")
    url = f"{BASE_URL}/v2/auth/credentials"
    data = {
        "hostname": credentials.hostname,
        "username": credentials.username,
        "password": credentials.password
    }
    if credentials.otp:
        data["otp"] = credentials.otp

    try:
        response = session.post(url=url, json=data, timeout=TIMEOUT_S)
        response.raise_for_status()
        access_token = response.json().get("accessToken")

        if not access_token:
            logger.error("Failed to obtain access token. Please check your credentials and try again.")
            return None
        return access_token
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred while obtaining access token: {e}")
        return None

def retrieve_licenses(*, session: requests.Session, headers: Dict[str, str]) -> Optional[Dict]:
    """
    Retrieve available licenses.
    """
    logger.info("Retrieving licenses...")
    url = f"{BASE_URL}/v2/licenses"
    try:
        response = session.get(url=url, headers=headers, timeout=TIMEOUT_S)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred while retrieving licenses: {e}")
        return None

def main():
    """
    Main function to run the script.
    """
    args = parse_arguments()
    password = getpass.getpass(prompt=f"Password for {args.hostname}/{args.username}: ")

    otp = None
    if args.hostname == "mi.metrc.com":
        otp = getpass.getpass(prompt="OTP: ")

    credentials = Credentials(hostname=args.hostname, username=args.username, password=password, otp=otp)

    with requests.Session() as session:
        access_token = obtain_access_token(session=session, credentials=credentials)
        if not access_token:
            sys.exit(1)

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        licenses = retrieve_licenses(session=session, headers=headers)
        if not licenses:
            logger.info("No licenses found.")
            sys.exit(1)

        logger.info("API access is configured correctly.")

if __name__ == "__main__":
    main()