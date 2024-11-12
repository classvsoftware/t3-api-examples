import csv
import getpass
import requests
import os
from datetime import datetime

# Constants
BASE_URL = "https://api.trackandtrace.tools"
USERNAME = "YOUR_USERNAME"  # Replace with your actual username
HOSTNAME = "ca.metrc.com"  # Update this to your specific Metrc hostname
OUTPUT_DIR = "output"
OUTPUT_CSV_TEMPLATE = os.path.join(OUTPUT_DIR, "transfers_{}.csv")


def get_access_token(hostname, username, password, otp=None):
    url = f"{BASE_URL}/v2/auth/credentials"
    data = {"hostname": hostname, "username": username, "password": password}
    if otp:
        data["otp"] = otp

    response = requests.post(url, json=data)
    response.raise_for_status()
    return response.json()["accessToken"]


def get_licenses(access_token):
    url = f"{BASE_URL}/v2/licenses"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_outgoing_transfers(access_token, license_number):
    url = f"{BASE_URL}/v2/transfers/outgoing/active?licenseNumber={license_number}&pageSize=500"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]


def write_transfers_to_csv(transfers, output_file):
    if not transfers:
        print("No transfers found.")
        return

    keys = transfers[0].keys()  # Use the first transfer's keys for the CSV headers

    with open(output_file, "w", newline="") as output:
        dict_writer = csv.DictWriter(output, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(transfers)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_stamp = datetime.now().strftime("%Y%m%d")
    output_file = OUTPUT_CSV_TEMPLATE.format(date_stamp)

    password = getpass.getpass(prompt=f"Password for {HOSTNAME}/{USERNAME}: ")
    otp = None
    if HOSTNAME == "mi.metrc.com":
        otp = getpass.getpass(prompt="OTP: ")
    try:
        access_token = get_access_token(HOSTNAME, USERNAME, password, otp)
        licenses = get_licenses(access_token)

        # Display licenses and ask the user to select one
        print("Select a license:")
        for idx, license in enumerate(licenses, 1):
            print(f"{idx}. {license['licenseNumber']} - {license['licenseName']}")

        selected_idx = int(input("Enter the number of the license to select: ")) - 1
        selected_license = licenses[selected_idx]
        selected_license_number = selected_license["licenseNumber"]

        transfers = get_outgoing_transfers(access_token, selected_license_number)

        print(transfers)
        write_transfers_to_csv(transfers, output_file)
        print(f"Transfers have been written to {output_file}")

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
    except Exception as e:
        print(e)
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
