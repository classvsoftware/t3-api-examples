import getpass
import sys

from t3api import ApiClient, Configuration
from t3api.api.authentication_api import AuthenticationApi
from t3api.api.licenses_api import LicensesApi

if len(sys.argv) != 3:
    print("Usage: python script.py <hostname> <username>")
    sys.exit(1)

hostname = sys.argv[1]
username = sys.argv[2]
password = getpass.getpass("Password: ")

# Set up configuration
config = Configuration(host=f"https://api.trackandtrace.tools")
config.debug = False

with ApiClient(config) as client:
    auth_api = AuthenticationApi(client)
    login_payload = {"hostname": hostname, "username": username, "password": password}
    response = auth_api.v2_auth_credentials_post(login_payload)

    token = response.access_token  # Assumes the token is returned in this field

    # Step 2: Set the token on the configuration
    config.access_token = token  # This enables automatic header injection
     
    license_response = LicensesApi(client).v2_licenses_get()
    
    for license in license_response:
        print(license.license_name)
    
    