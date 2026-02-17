#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "t3api_utils>=1.4.0"
# ]
# ///
#
# T3 API - Getting Started
#
# 1. Download this file: https://github.com/classvsoftware/t3-api-examples/blob/master/intro.py
#
# 2. Install uv (a fast Python tool that handles everything for you, including Python itself):
#    https://docs.astral.sh/uv/getting-started/installation/
#
# 3. Open a terminal, navigate to where you saved this file, and run:
#    uv run intro.py
#

from t3api_utils.intro import run_intro

run_intro()
