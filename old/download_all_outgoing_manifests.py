import csv
import getpass
import os
from datetime import datetime

import requests

# Constants
BASE_URL = "https://api.trackandtrace.tools"
USERNAME = "YOUR_USERNAME"  # Replace with your actual username
HOSTNAME = "ca.metrc.com"  # Update this to your specific Metrc hostname
OUTPUT_DIR = "output"  # Directory to store the output files

def get_access_token(hostname, username, password, otp=None):
    """
    Obtain an access token for API authentication.

    :param hostname: The hostname of the Metrc instance.
    :param username: The username for authentication.
    :param password: The password for authentication.
    :param otp: One-Time Password, if required.
    :return: Access token as a string.
    """
    url = f"{BASE_URL}/v2/auth/credentials"
    data = {"hostname": hostname, "username": username, "password": password}
    if otp:
        data["otp"] = otp

    response = requests.post(url, json=data)
    response.raise_for_status()
    return response.json()["accessToken"]


def get_licenses(access_token):
    """
    Retrieve a list of licenses from the API.

    :param access_token: The access token for authentication.
    :return: A list of license data.
    """
    url = f"{BASE_URL}/v2/licenses"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_outgoing_transfers(access_token, license_number):
    """
    Retrieve a list of outgoing transfers for a specific license.

    :param access_token: The access token for authentication.
    :param license_number: The license number to query.
    :return: A list of outgoing transfers.
    """
    url = f"{BASE_URL}/v2/transfers/outgoing/active"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    params = {"licenseNumber": license_number}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()["data"]


def download_manifest_pdf(access_token, license_number, manifest_number):
    """
    Download the manifest PDF for a specific transfer.

    :param access_token: The access token for authentication.
    :param license_number: The license number.
    :param manifest_number: The manifest number of the transfer.
    """
    url = f"{BASE_URL}/v2/transfers/manifest"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    params = {"licenseNumber": license_number, "manifestNumber": manifest_number}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    license_dir = os.path.join(OUTPUT_DIR, "manifests", license_number)
    os.makedirs(license_dir, exist_ok=True)

    pdf_path = os.path.join(license_dir, f"{manifest_number}.pdf")
    with open(pdf_path, "wb") as file:
        file.write(response.content)
    print(f"Downloaded manifest PDF: {pdf_path}")



def main():
    """
    Main function to run the script.
    """
    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    password = getpass.getpass(prompt=f"Password for {HOSTNAME}/{USERNAME}: ")
    otp = None
    if HOSTNAME == "mi.metrc.com":  # Check if OTP is required
        otp = getpass.getpass(prompt="OTP: ")
    try:
        access_token = get_access_token(HOSTNAME, USERNAME, password, otp)
        licenses = get_licenses(access_token)

        # Download manifest PDFs for each license's outgoing transfers
        for license in licenses:
            license_number = license["licenseNumber"]
            outgoing_transfers = get_outgoing_transfers(access_token, license_number)
            for transfer in outgoing_transfers:
                manifest_number = transfer["manifestNumber"]
                download_manifest_pdf(access_token, license_number, manifest_number)

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
