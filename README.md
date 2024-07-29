# t3-api

These are example python scripts that use the [T3 API](https://api.trackandtrace.tools/v2/docs/) to automatically talk to metrc.com

## Examples

- [license_data_csv.py](license_data_csv.py) is a simple introductory script that securely reads the user's password in the command line, authenticates with the API, loads the active licenses, and writes the data to a CSV file
- [load_all_active_packages.py](load_all_active_packages.py) shows how to load a large number of packages, one page at a time, and writes the package data to a CSV file
- [download_all_outgoing_manifests.py](download_all_outgoing_manifests.py) shows how to download manifest PDFs into one directory, separated by the parent license number
