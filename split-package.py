#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils",
#     "questionary"
# ]
# ///

# Usage:    uv run split-package.py
#
# This script walks you through splitting an existing package into a new one.
#
# "Splitting" a package means taking some quantity from a source package and
# creating a new package from it. For example, you might split 5 grams out of
# a 100-gram source package into a new package with its own tag.
#
# The script will:
#   1. Authenticate you with the T3 API
#   2. Let you pick a license to work under
#   3. Load all available source packages, items, and tags
#   4. Prompt you through each decision (which package to split, how much, etc.)
#   5. Submit the new package creation request to the API

from datetime import date
from typing import NotRequired, TypedDict

import questionary
from t3api_utils.api.operations import send_api_request
from t3api_utils.api.parallel import load_all_data_sync
from t3api_utils.main.utils import (get_authenticated_client_or_error,
                                    match_collection_from_csv, pick_license)


# ---------------------------------------------------------------------------
# Type definitions
#
# These TypedDict classes describe the shape of JSON objects returned by
# (or sent to) the T3 API. They help your editor provide autocomplete and
# catch typos when accessing dictionary keys.
# ---------------------------------------------------------------------------


class PackageItem(TypedDict):
    """The item (product type) associated with a package.

    Every package is linked to an "item" which defines what kind of product
    it contains (e.g. "Biomass", "Concentrate", etc.).
    """

    id: int
    """Unique item ID. e.g. 6645."""


class SourceItem(TypedDict):
    """An available item that can be assigned to a new package.

    Returned by GET /v2/packages/create/source-items. When creating a new
    package, you can either reuse the source package's item or pick a
    different one from this list.
    """

    id: int
    """Unique item ID. e.g. 6645."""
    name: str
    """Display name. e.g. "SBX Biomass SBX Strain 1 Item"."""


class SourcePackage(TypedDict):
    """An existing package that can be used as a source for splitting.

    Returned by GET /v2/packages/create/source-packages. Each source package
    has a unique tag label (like a barcode) and a quantity you can pull from.
    """

    id: int
    """Unique package ID. e.g. 15481."""
    item: PackageItem
    """The item associated with this package."""
    label: str
    """Package tag label. e.g. "AAAFF03000001F9000001001"."""
    unitOfMeasureId: int
    """Unit of measure ID for this package's quantity. e.g. 4 (Pounds)."""


class SourceTag(TypedDict):
    """A tag that can be assigned to a new package.

    Tags are unique identifiers (like barcodes) that get physically attached
    to packages. Each new package needs an unused tag. Returned by
    GET /v2/packages/create/source-tags.
    """

    id: int
    """Unique tag ID. e.g. 1527333."""
    label: str
    """Tag label. e.g. "AAAFF03000001F9000001001"."""


class Location(TypedDict):
    """A physical location within a facility where packages can be stored."""

    id: int
    """Unique location ID. e.g. 581."""
    name: str
    """Display name of the location. e.g. "SBX Default Location 1"."""


class UnitOfMeasure(TypedDict):
    """A unit of measure for quantities (weight, volume, or count)."""

    abbreviation: str
    """Short abbreviation. e.g. "g", "oz", "lb", "ml", "ea"."""
    id: int
    """Unique unit of measure ID. e.g. 2."""
    name: str
    """Display name. e.g. "Grams", "Ounces", "Pounds"."""


class PackageInputs(TypedDict):
    """Lookup data needed to create a package.

    Returned by GET /v2/packages/create/inputs. Contains the lists of
    available locations and units of measure for the selected license.
    """

    locations: list[Location]
    """Available facility locations."""
    unitsOfMeasure: list[UnitOfMeasure]
    """Available units of measure."""


class Ingredient(TypedDict):
    """Describes how much to pull from a source package.

    When creating a new package, you specify one or more "ingredients" --
    each ingredient references a source package and says how much quantity
    to take from it.

    Example::

        {
            "packageId": 5077333,
            "quantity": 56.3,
            "unitOfMeasureId": 4
        }
    """

    finishDate: NotRequired[str]
    """Optional date to mark the source package as finished (YYYY-MM-DD).
    If set, the source package will be closed out on this date."""
    packageId: int
    """ID of the source package to pull from."""
    quantity: float
    """Amount to pull from the source package. e.g. 56.3."""
    unitOfMeasureId: int
    """Unit of measure for the quantity. e.g. 4 (Pounds)."""


class CreatePackageBody(TypedDict):
    """The request body sent to POST /v2/packages/create.

    This is the final payload that tells the API everything it needs to
    create the new package: what to pull from (ingredients), how much to
    produce (quantity), where to store it (locationId), and what tag to
    assign (tagId).

    Example::

        {
            "actualDate": "2024-08-08",
            "ingredients": [{"packageId": 5077333, "quantity": 56.3, "unitOfMeasureId": 4}],
            "itemId": 1160223,
            "locationId": 50901,
            "quantity": 123.45,
            "unitOfMeasureId": 1
        }
    """

    actualDate: str
    """Date the package was created (YYYY-MM-DD)."""
    ingredients: list[Ingredient]
    """List of source packages and quantities to pull from."""
    itemId: int
    """Item (product type) ID for the new package."""
    locationId: int
    """Location ID where the new package will be stored."""
    quantity: float
    """Output quantity for the new package."""
    tagId: int
    """Tag ID to assign to the new package."""
    unitOfMeasureId: int
    """Unit of measure for the output quantity."""
    useSameItem: NotRequired[bool]
    """If True, the new package keeps the same item as the source package."""


def main():
    # -----------------------------------------------------------------------
    # Step 1: Authenticate
    #
    # This prompts you to log in. You can authenticate via username/password,
    # a JWT token (from the T3 Chrome extension), or an API key.
    # -----------------------------------------------------------------------
    api_client = get_authenticated_client_or_error()

    # -----------------------------------------------------------------------
    # Step 2: Pick a license
    #
    # Each facility operates under a license. This lets you choose which
    # license (and therefore which facility's data) you want to work with.
    # -----------------------------------------------------------------------
    license = pick_license(api_client=api_client)

    # -----------------------------------------------------------------------
    # Step 3: Load reference data from the API
    #
    # We need to fetch all available source packages, items, tags, locations,
    # and units of measure before we can present choices to the user.
    # -----------------------------------------------------------------------

    # All active packages that can be split from
    packages: list[SourcePackage] = load_all_data_sync(
        client=api_client,
        path="/v2/packages/create/source-packages",
        license_number=license["licenseNumber"],
    )

    # All items (product types) that can be assigned to a new package
    items: list[SourceItem] = load_all_data_sync(
        client=api_client,
        path="/v2/packages/create/source-items",
        license_number=license["licenseNumber"],
    )

    # All unused tags available for assignment to a new package
    tags: list[SourceTag] = load_all_data_sync(
        client=api_client,
        path="/v2/packages/create/source-tags",
        license_number=license["licenseNumber"],
    )

    # Locations and units of measure for the selected license
    package_inputs: PackageInputs = send_api_request(
        client=api_client,
        path="/v2/packages/create/inputs",
        method="GET",
        params={
            "licenseNumber": license["licenseNumber"],
        },
    )

    locations = package_inputs["locations"]
    units_of_measure = package_inputs["unitsOfMeasure"]

    # -----------------------------------------------------------------------
    # Step 4: Collect user inputs
    #
    # Walk the user through each decision needed to create the new package.
    # -----------------------------------------------------------------------

    # Pick which existing package to split from
    source_package = questionary.select(
        "Select source package:",
        choices=[
            questionary.Choice(title=p["label"], value=p)
            for p in packages
        ],
    ).ask()
    source_package_id = source_package["id"]

    # The new package can keep the same item (product type) as the source,
    # or you can assign a different item.
    use_same_item = questionary.confirm(
        "Use same item as source package?",
        default=True,
    ).ask()

    if use_same_item:
        # Reuse the source package's item
        item_id = source_package["item"]["id"]
    else:
        # Let the user pick a different item from all available items
        item_id = questionary.select(
            "Select item:",
            choices=[
                questionary.Choice(title=i["name"], value=i["id"])
                for i in items
            ],
        ).ask()

    # When was this package actually created? Defaults to today.
    today = date.today().isoformat()
    actual_date = input(f"Actual date (YYYY-MM-DD) [{today}]: ") or today

    # Optional: if the source package should be marked as "finished" (fully
    # used up) on a specific date, enter it here. Leave blank to skip.
    finish_date = input("Finish date (YYYY-MM-DD) [skip]: ")

    # How much to pull from the source package
    ingredient_quantity = float(input("Ingredient quantity: "))

    # What unit is that quantity in (grams, ounces, etc.)
    # When using the same item, default to the source package's unit of measure.
    uom_choices = [
        questionary.Choice(title=f"{u['name']} ({u['abbreviation']})", value=u["id"])
        for u in units_of_measure
    ]
    default_uom_id = source_package["unitOfMeasureId"] if use_same_item else None

    ingredient_uom_id = questionary.select(
        "Select ingredient unit of measure:",
        choices=uom_choices,
        default=default_uom_id,
    ).ask()

    # Where to store the new package
    location_id = questionary.select(
        "Select location:",
        choices=[
            questionary.Choice(title=u["name"], value=u["id"])
            for u in locations
        ],
    ).ask()

    # How much the new package will contain (may differ from ingredient
    # quantity due to processing loss, unit conversion, etc.)
    # If using the same item and same UoM, default to the ingredient quantity.
    if use_same_item and ingredient_uom_id == default_uom_id:
        output_quantity_str = input(f"Output quantity [{ingredient_quantity}]: ")
        output_quantity = float(output_quantity_str) if output_quantity_str else ingredient_quantity
    else:
        output_quantity = float(input("Output quantity: "))

    # What unit is the output quantity in
    # Also defaults to the source package's unit of measure when using the same item.
    output_uom_id = questionary.select(
        "Select output unit of measure:",
        choices=uom_choices,
        default=default_uom_id,
    ).ask()

    # Pick an unused tag to assign to the new package
    tag_id = questionary.select(
        "Select tag:",
        choices=[
            questionary.Choice(title=t["label"], value=t["id"])
            for t in tags
        ],
    ).ask()

    # -----------------------------------------------------------------------
    # Step 5: Build and submit the API request
    #
    # Assemble the ingredient (what to pull from) and the package body
    # (what to create), then POST it to the API.
    # -----------------------------------------------------------------------

    # The ingredient describes what we're pulling from the source package
    ingredient: Ingredient = {
        "packageId": source_package_id,
        "quantity": ingredient_quantity,
        "unitOfMeasureId": ingredient_uom_id,
    }
    if finish_date:
        ingredient["finishDate"] = finish_date

    # The body describes the new package we're creating
    body: CreatePackageBody = {
        "actualDate": actual_date,
        "ingredients": [ingredient],
        "itemId": item_id,
        "locationId": location_id,
        "quantity": output_quantity,
        "tagId": tag_id,
        "unitOfMeasureId": output_uom_id,
    }
    if use_same_item:
        body["useSameItem"] = True

    # Submit the request. The API expects a list of package bodies (to
    # support batch creation), so we wrap our single body in a list.
    send_api_request(
        client=api_client,
        path="/v2/packages/create",
        method="POST",
        params={"licenseNumber": license["licenseNumber"], "submit": True},
        json_body=[body],
    )


if __name__ == "__main__":
    main()
