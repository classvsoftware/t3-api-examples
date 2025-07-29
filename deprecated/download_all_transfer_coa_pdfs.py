import getpass
import os
from datetime import datetime

import requests

# Constants
BASE_URL = "https://api.trackandtrace.tools"
USERNAME = "YOUR_USERNAME"  # Replace with your actual username
HOSTNAME = "ca.metrc.com"  # Update this to your specific Metrc hostname
OUTPUT_DIR = "output"  # Directory to store the output files
COA_FILE_TEMPLATE = os.path.join(
    OUTPUT_DIR, "coa_{id}.pdf"
)  # Template for the COA file name


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


def get_outgoing_transfer(access_token, license_number, manifest_number):
    url = f"{BASE_URL}/v2/transfers/outgoing/active?licenseNumber={license_number}&filter=manifestNumber__contains:{manifest_number}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    transfers = response.json()["data"]
    if not transfers:
        raise ValueError(f"No transfer found with manifest number {manifest_number}")
    return transfers[0]


def get_transfer_destinations(access_token, license_number, manifest_number):
    url = f"{BASE_URL}/v2/transfers/deliveries?licenseNumber={license_number}&manifestNumber={manifest_number}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]


def get_destination_packages(access_token, license_number, delivery_id):
    url = f"{BASE_URL}/v2/transfers/packages?licenseNumber={license_number}&deliveryId={delivery_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]


def get_package_lab_results(access_token, license_number, package_id):
    url = f"{BASE_URL}/v2/packages/labresults?licenseNumber={license_number}&packageId={package_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]


def download_lab_result_pdf(
    access_token, license_number, lab_result_document_file_id, package_id
):
    url = f"{BASE_URL}/v2/packages/labresults/document?licenseNumber={license_number}&labTestResultDocumentFileId={lab_result_document_file_id}&packageId={package_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers, stream=True)
    response.raise_for_status()
    file_path = COA_FILE_TEMPLATE.format(id=lab_result_document_file_id)
    with open(file_path, "wb") as f:
        f.write(response.content)
    print(f"Downloaded COA PDF to {file_path}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

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

        # Input manifest number and validate
        manifest_number = input("Enter the manifest number: ")
        if not manifest_number.isdigit():
            raise ValueError("Manifest number must be a string of digits.")

        # Get outgoing transfer and all related data
        transfer = get_outgoing_transfer(
            access_token, selected_license_number, manifest_number
        )
        destinations = get_transfer_destinations(
            access_token, selected_license_number, manifest_number
        )

        # Set to store unique lab result document IDs
        lab_result_document_ids = set()

        # Iterate through destinations and packages to find lab results
        for destination in destinations:
            delivery_id = destination["id"]
            packages = get_destination_packages(
                access_token, selected_license_number, delivery_id
            )
            for package in packages:
                package_id = package["packageId"]
                lab_results = get_package_lab_results(
                    access_token, selected_license_number, package_id
                )
                for lab_result in lab_results:
                    lab_result_document_id = lab_result.get(
                        "labTestResultDocumentFileId"
                    )
                    if lab_result_document_id:
                        lab_result_document_ids.add(
                            (package_id, lab_result_document_id)
                        )

        # Download each lab result document
        for package_id, lab_result_document_id in lab_result_document_ids:
            download_lab_result_pdf(
                access_token,
                selected_license_number,
                lab_result_document_id,
                package_id,
            )

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
