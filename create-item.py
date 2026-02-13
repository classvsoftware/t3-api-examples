#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "t3api_utils",
#     "questionary"
# ]
# ///

# Usage:    uv run create-item.py
#
# This script walks you through creating a new item (product type) in Metrc.
#
# An "item" defines a product type that can be assigned to packages.
# For example, "Blue Dream Flower" or "Wedding Cake Concentrate".
#
# The script will:
#   1. Authenticate you with the T3 API
#   2. Let you pick a license to work under
#   3. Load item categories, strains (if needed), and units of measure
#   4. Prompt you through each required field
#   5. Submit the new item creation request to the API

from typing import NotRequired, TypedDict

import questionary
from t3api_utils.api.operations import send_api_request
from t3api_utils.api.parallel import load_all_data_sync
from t3api_utils.main.utils import (get_authenticated_client_or_error,
                                    pick_license)

# ---------------------------------------------------------------------------
# Type definitions
#
# These TypedDict classes describe the shape of JSON objects returned by
# (or sent to) the T3 API. They help your editor provide autocomplete and
# catch typos when accessing dictionary keys.
# ---------------------------------------------------------------------------


class ItemCategory(TypedDict):
    """A product category that an item can belong to.

    Returned inside the response from GET /v2/items/create/inputs.
    Each category defines what kind of product the item represents
    (e.g. "Biomass", "Concentrate", "Edible").
    """

    id: int
    """Unique category ID. e.g. 301."""
    name: str
    """Display name. e.g. "Biomass"."""
    requiresStrain: bool
    """Whether this category requires a strain to be specified."""
    quantityType: str
    """Measurement type. e.g. "WeightBased", "CountBased"."""


class Strain(TypedDict):
    """A cannabis strain that can be associated with an item.

    Returned by GET /v2/strains. Strains describe the genetic
    variety of the cannabis plant (e.g. "Wedding Cake", "Blue Dream").
    """

    id: int
    """Unique strain ID. e.g. 737."""
    name: str
    """Strain name. e.g. "Wedding Cake"."""


class UnitOfMeasure(TypedDict):
    """A unit of measure for quantities (weight, volume, or count)."""

    abbreviation: str
    """Short abbreviation. e.g. "g", "oz", "lb", "ml", "ea"."""
    id: int
    """Unique unit of measure ID. e.g. 2."""
    name: str
    """Display name. e.g. "Grams", "Ounces", "Pounds"."""


class ItemInputs(TypedDict):
    """Lookup data needed to create an item.

    Returned by GET /v2/items/create/inputs. Contains the list of
    available item categories for the selected license.
    """

    adding: bool
    """Whether items can be added under this license."""
    items: list | None
    """Existing items (may be null)."""
    itemBrands: list | None
    """Available item brands (may be null)."""
    itemCategories: list[ItemCategory]
    """Available product categories."""


class CreateItemBody(TypedDict):
    """The request body sent to POST /v2/items/create.

    This is the final payload that tells the API everything it needs to
    create the new item: what to name it, what category it belongs to,
    what strain it is, and what unit of measure it uses.

    Example::

        {
            "name": "Blue Dream Flower",
            "productCategoryId": 301,
            "strainId": 737,
            "unitOfMeasureId": 2
        }
    """

    name: str
    """The name of the item. e.g. "Blue Dream Flower"."""
    productCategoryId: int
    """Product category ID for this item."""
    strainId: NotRequired[int]
    """Strain ID associated with this item. Only needed when the selected
    product category requires a strain."""
    unitOfMeasureId: int
    """Unit of measure ID for this item's default quantity."""


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
    # We need to fetch item categories and units of measure before we can
    # present choices to the user. Strains are loaded later only if the
    # selected category requires one.
    # -----------------------------------------------------------------------

    # Item categories and other inputs for item creation
    item_inputs: ItemInputs = send_api_request(
        client=api_client,
        path="/v2/items/create/inputs",
        method="GET",
        params={
            "licenseNumber": license["licenseNumber"],
        },
    )

    item_categories = item_inputs["itemCategories"]

    # Units of measure (fetched from packages inputs, as the items inputs
    # endpoint does not include them)
    package_inputs = send_api_request(
        client=api_client,
        path="/v2/packages/create/inputs",
        method="GET",
        params={
            "licenseNumber": license["licenseNumber"],
        },
    )

    units_of_measure: list[UnitOfMeasure] = package_inputs["unitsOfMeasure"]

    # -----------------------------------------------------------------------
    # Step 4: Collect user inputs
    #
    # Walk the user through each required field for item creation.
    # -----------------------------------------------------------------------

    # Enter the item name
    name = questionary.text("Item name:").ask()

    # Pick a product category
    product_category_id = questionary.select(
        "Select product category:",
        choices=[
            questionary.Choice(title=c["name"], value=c["id"])
            for c in item_categories
        ],
    ).ask()

    # Pick a strain (only if the selected category requires one)
    selected_category = next(
        c for c in item_categories if c["id"] == product_category_id
    )
    strain_id = None
    if selected_category["requiresStrain"]:
        strains: list[Strain] = load_all_data_sync(
            client=api_client,
            path="/v2/strains",
            license_number=license["licenseNumber"],
        )
        strain_id = questionary.select(
            "Select strain:",
            choices=[
                questionary.Choice(title=s["name"], value=s["id"])
                for s in strains
            ],
        ).ask()

    # Pick a unit of measure
    unit_of_measure_id = questionary.select(
        "Select unit of measure:",
        choices=[
            questionary.Choice(
                title=f"{u['name']} ({u['abbreviation']})", value=u["id"]
            )
            for u in units_of_measure
        ],
    ).ask()

    # -----------------------------------------------------------------------
    # Step 5: Build and submit the API request
    #
    # Assemble the item body and POST it to the API.
    # -----------------------------------------------------------------------

    body: CreateItemBody = {
        "name": name,
        "productCategoryId": product_category_id,
        "unitOfMeasureId": unit_of_measure_id,
    }
    if strain_id is not None:
        body["strainId"] = strain_id

    # Ask whether to submit to Metrc for real, or just save as a draft.
    # submit=True sends the item to Metrc immediately and creates it.
    # submit=False saves it as a draft in T3 that can be reviewed first.
    submit = questionary.confirm(
        "Submit to Metrc and create the item now?",
        default=False,
    ).ask()

    # The API expects a list of item bodies (to support batch creation),
    # so we wrap our single body in a list.
    send_api_request(
        client=api_client,
        path="/v2/items/create",
        method="POST",
        params={"licenseNumber": license["licenseNumber"], "submit": submit},
        json_body=[body],
    )


if __name__ == "__main__":
    main()
