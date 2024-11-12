# Loads all active packages and writes the package data to a CSV
#
# To run this script from the command line, use:
# python load_all_active_packages.py

import csv
import getpass
import os  # Import os for directory management
from datetime import datetime  # Import datetime for date stamping

import requests

# Constants
BASE_URL = "https://api.trackandtrace.tools"
USERNAME = "YOUR_USERNAME"  # Replace with your actual username
HOSTNAME = "ca.metrc.com"  # Update this to your specific Metrc hostname
LICENSE_NUMBER = "LIC-00001"  # Replace with the actual license number
OUTPUT_DIR = "output"  # Directory for output files
OUTPUT_CSV_TEMPLATE = os.path.join(OUTPUT_DIR, "packages_{}.csv")  # Template for the output file name


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
    response.raise_for_status()  # Raise an error for bad responses
    return response.json()["accessToken"]


def get_packages(access_token, license_number, page_size=500):
    """
    Retrieve all active packages from the API for a given license number.

    :param access_token: The access token for authentication.
    :param license_number: The license number for which to fetch packages.
    :param page_size: Number of records per page (default is 500).
    :return: A list of all packages data.
    """
    page = 1
    all_packages = []
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    while True:
        url = f"{BASE_URL}/v2/packages/active?licenseNumber={license_number}&page={page}&pageSize={page_size}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        packages = response.json().get("data", [])
        if not packages:
            break

        all_packages.extend(packages)
        page += 1

    return all_packages


def write_packages_to_csv(packages, output_file):
    """
    Write the package data to a CSV file.

    :param packages: List of packages to write.
    :param output_file: File path for the output CSV.
    """
    if not packages:
        print("No packages found.")
        return

    # Create the output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    keys = packages[0].keys()  # Use the first package's keys for the CSV headers
    with open(output_file, "w", newline="") as output:
        dict_writer = csv.DictWriter(output, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(packages)


def main():
    """
    Main function to run the script.
    Prompts the user for password (and OTP if required), retrieves packages, and writes them to a CSV file.
    """
    # Get the current date and format it as YYYYMMDD
    date_stamp = datetime.now().strftime("%Y%m%d")
    # Generate the output file name with the date stamp
    output_file = OUTPUT_CSV_TEMPLATE.format(date_stamp)

    password = getpass.getpass(prompt=f"Password for {HOSTNAME}/{USERNAME}: ")
    otp = None
    if HOSTNAME == "mi.metrc.com":  # Check if OTP is required
        otp = getpass.getpass(prompt="OTP: ")
    try:
        access_token = get_access_token(HOSTNAME, USERNAME, password, otp)

        packages = get_packages(access_token, LICENSE_NUMBER)
        write_packages_to_csv(packages, output_file)
        print(f"Packages have been written to {output_file}")

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()

