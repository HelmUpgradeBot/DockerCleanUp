"""
Script to delete images from an ACR that are 90 days older or more.
Requires the name of the ACR to delete images from.

Usage:
    NAME="<registry-name>" python DockerCleanUpBot.py --dry-run

Requirements:
  - pandas
"""

import os
import json
import logging
import argparse
import pandas as pd
from subprocess import check_call, check_output

# Get environment variable
REGISTRY_NAME = os.environ.get("NAME")

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do a dry-run, no images will be deleted."
    )

    return parser.parse_args()

def main():
    args = parse_args()

    if args.dry_run:
        logging.info("THIS IS A DRY RUN.  NO IMAGES WILL BE DELETED.")

    # Set-up
    images_to_be_deleted_number = 0
    images_to_be_deleted_digest = []

    # Login
    logging.info("--> Login to Azure")
    check_call("az login --identity -o none", shell=True)
    logging.info("--> Login to ACR")
    check_call(f"az acr login -n {REGISTRY_NAME}", shell=True)

    # Get the repositories in the ACR
    logging.info("--> Fetching repositories")
    output = check_output(
        f"az acr repository list -n {REGISTRY_NAME} -o tsv",
        shell=True
    ).decode()
    REPOS = output.split("\n")[:-1]

    # Loop over the repositories
    for REPO in REPOS:
        # Get the manifest for the current repository
        output = check_output(
            f"az acr repository show-manifests -n {REGISTRY_NAME} --repository {REPO} --orderby time_desc",
            shell=True
        ).decode()
        outputs = output.replace("\n", "").replace(" ", "")[1:-1].split("},")

        # Loop over the manifests for each repository
        for j, output in enumerate(outputs):
            if j < (len(outputs) - 1):
                output += "}"

            # Convert the manifest to a dict and extract timestamp
            MANIFEST = json.loads(output)
            timestamp = pd.to_datetime(MANIFEST["timestamp"]).tz_localize(None)

            # Get time difference between now and the manifest timestamp
            diff = (pd.Timestamp.now() - timestamp).days

            # If an image is 90 days old or more, delete it
            if diff >= 90:
                images_to_be_deleted_digest.append(f"{REPO}@{MAINFEST['digest']}")
                images_to_be_deleted_number += 1

    if args.dry_run:
        logging.info(f"Number of images eligible for deletion: {images_to_be_deleted_number}")
    else:
        logging.info(f"Number of images to be deleted: {images_to_be_deleted_number}")

        for image in images_to_be_deleted_digest:
            logging.info(f"--> Deleting image: {image}")
            check_call(
                f"az acr repository delete -n {REGISTRY_NAME} --image {image}",
                shell=True
            )

if __name__ == "__main__":
    main()
