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
import subprocess
import pandas as pd

# Get environment variable
REGISTRY_NAME = os.environ.get("NAME")

# Set up logging config
logging.basicConfig(
    level=logging.DEBUG,
    filename="DockerCleanUpBot.log",
    filemode="a",
    format="[%(asctime)s %(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

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
        logging.info("THIS IS A DRY RUN. NO IMAGES WILL BE DELETED.")

    # Set-up
    images_to_be_deleted_number = 0
    images_to_be_deleted_digest = []
    deleted_images_total = 0

    # Login to Azure
    logging.info("Login to Azure")
    proc = subprocess.Popen(
        ["az", "login", "--identity"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if proc.returncode == 0:
        logging.info("Successfully logged into Azure")
    else:
        err_msg = proc.communicate()[1].decode(encoding="utf-8")
        logging.error(err_msg)

    # Login in to ACR
    logging.info("Login to ACR")
    proc = subprocess.Popen(
        ["az", "acr", "login", "-n", REGISTRY_NAME],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    res = proc.communicate()
    if proc.returncode == 0:
        logging.info(f"Successfully logged into ACR: {REGISTRY_NAME}")
    else:
        err_msg = res[1].decode(encoding="utf-8")
        logging.error(f"{err_msg}")

    # Get the repositories in the ACR
    logging.info(f"Fetching repositories in: {REGISTRY_NAME}")
    proc = subprocess.Popen(
        ["az", "acr", "repository", "list", "-n", REGISTRY_NAME, "-o", "tsv"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    res = proc.communicate()
    if proc.returncode == 0:
        logging.info(f"Successfully fetched repositories from: {REGISTRY_NAME}")
        output = res[0].decode(encoding="utf-8")
        REPOS = output.split("\n")[:-1]
        logging.info(f"Total number of repositories: {len(REPOS)}")
    else:
        err_msg = res[1].decode(encoding="utf-8")
        logging.error(err_msg)

    # Loop over the repositories
    logging.info("Checking repository manifests")
    for REPO in REPOS:
        # Get the manifest for the current repository
        proc = subprocess.Popen(
            [
                "az", "acr", "repository", "show-manifests", "-n",
                REGISTRY_NAME, "--repository", REPO, "--orderby", "time_desc"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        res = proc.communicate()
        if proc.returncode == 0:
            logging.info(f"Successfully pulled manifests for: {REPO}")
            output = res[0].decode(encoding="utf-8")
            outputs = output.replace("\n", "").replace(" ", "")[1:-1].split("},")
            logging.info(f"Total number of manifests in {REPO}: {len(outputs)}")
        else:
            err_msg = res[1].decode(encoding="utf-8")
            logging.error(err_msg)

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
                logging.info(f"{REPO}@{MANIFEST['digest']} is {diff} days old.")
                images_to_be_deleted_digest.append(f"{REPO}@{MANIFEST['digest']}")
                images_to_be_deleted_number += 1

    if args.dry_run:
        logging.info(f"Number of images eligible for deletion: {images_to_be_deleted_number}")
    else:
        logging.info(f"Number of images to be deleted: {images_to_be_deleted_number}")

        for image in images_to_be_deleted_digest:
            logging.info(f"Deleting image: {image}")
            proc = subprocess.Popen(
                [
                    "az", "acr", "repository", "delete", "-n", REGISTRY_NAME,
                    "--image", image
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            res = proc.communicate()
            if proc.returncode == 0:
                logging.info(f"Successfully deleted image: {image}")
                deleted_images_total += 1
            else:
                err_msg = res[1].decode(encoding="utf-8")
                logging.error(err_msg)

        logging.info(f"Number of images deleted: {deleted_images_total}")

if __name__ == "__main__":
    main()
