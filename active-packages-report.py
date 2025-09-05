# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "t3api",
#     "t3api-utils",
# ]
# ///


from t3api.api.packages_api import PackagesApi
from t3api.models.metrc_package import MetrcPackage
from t3api_utils.main.utils import (get_authenticated_client_or_error,
                                    pick_license)

api_client = get_authenticated_client_or_error()

license = pick_license(api_client=api_client)

# active_packages_report = PackagesApi(api_client=api_client).v2_packages_active_report_get(license_number=license.license_number)
active_packages_report = PackagesApi(api_client=api_client).v2_packages_active_get(
    license_number=license.license_number
)

# print(active_packages_report)
