"""
Script to delete images from an ACR that are 90 days older or more.
Requires some environment variables to log into the Azure account.

Usage:
    USERNAME="<username>" PASSWORD="<password>" TENANT="<tenant-id>"
    SUB="<subscription-name>" NAME="<registry-name>" python delete-old-images.py
    --dry-run

Requirements:
  - pandas

TODO:
  - Remove dependency on environment variables for login. Deploy as an Azure
    function with a Managed Identity.
"""

import os
import json
import argparse
import pandas as pd
from subprocess import check_call, check_output

# Get environment variables
USERNAME = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")
TENANT_ID = os.environ.get("TENANT")
SUBSCRIPTION = os.environ.get("SUB")
REGISTRY_NAME = os.environ.get("NAME")

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do a dry-run, no images will be deleted."
    )

    return parser.parse_args()

def main(dry_run=True):
    if dry_run:
        print("THIS IS A DRY RUN.  NO IMAGES WILL BE DELETED.")

    print("--> Login to Azure and set subscription")
    check_call([
        "az", "login", "--service-principal", "-u", USERNAME, "-p", PASSWORD,
        "--tenant", TENANT_ID
    ])
    check_call(["az", "account", "set", "-s", SUBSCRIPTION])

    print("--> Login to ACR")
    check_call(["az", "acr", "login", "-n", REGISTRY_NAME])

    print("--> Fetching repositories")
    # Get the repositories in the ACR
    output = check_output([
        "az", "acr", "repository", "list", "-n", REGISTRY_NAME, "-o", "tsv"
    ]).decode()
    REPOS = output.split("\n")[:-1]

    # Loop over the repositories
    for i, REPO in enumerate(REPOS):

        # Get the manifest for the current repository
        output = check_output([
            "az", "acr", "repository", "show-manifests", "-n", REGISTRY_NAME,
            "--repository", REPO, "--orderby", "time_desc"
        ]).decode()
        outputs = output.replace("\n", "").replace(" ", "")[1:-1].split("},")

        # Loop over the manifests for each repository
        for j, output in enumerate(outputs):
            if j < (len(outputs) - 1):
                output += "}"

            # Convert the manifest to a dict and extract timestamp
            MANIFEST = json.loads(output)
            timestamp = pd.to_datetime(MANIFEST["timestamp"])

            # Get time difference between now and the timestamp
            now = pd.Timestamp.now()
            diff = (now - timestamp).days

            # If an image is 90 days old or more, delete it
            if (diff >= 90) and (not dry_run):
                print(f"--> Deleting image: {REPO}@{MAINFEST['digest']}")
                check_call([
                    "az", "acr", "repository", "delete", "-n", REGISTRY_NAME,
                    "--image", f"{REPO}@{MAINFEST['digest']}"
                ])

if __name__ == "__main__":
    args = parse_args()
    main(dry_run=args.dry_run)
