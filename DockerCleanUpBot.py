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
from CustomExceptions import *
from run_command import run_cmd

# Set up logging config
logging.basicConfig(
    level=logging.DEBUG,
    filename="DockerCleanUpBot.log",
    filemode="a",
    format="[%(asctime)s %(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Script to clean old Docker images out of an Azure Container Registry"
    )

    parser.add_argument(
        "-n",
        "--name",
        type=str,
        required=True,
        help="Name of Azure Container Registry to clean"
    )
    parser.add_argument(
        "--identity",
        action="store_true",
        help="Login to Azure with a Managed System Identity"
    )
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
    login_cmd = ["az", "login"]
    if args.identity:
        login_cmd.append("--identity")
        logging.info("Login to Azure with Managed System Identity")
    else:
        logging.info("Login to Azure")

    result = run_cmd(login_cmd)
    if result["returncode"] == 0:
        logging.info("Successfully logged into Azure")
    else:
        logging.error(result["err_msg"])
        raise AzureError(result["err_msg"])

    # Login to ACR
    logging.info("Login to ACR")
    acr_cmd = ["az", "acr", "login", "-n", args.name]

    result = run_cmd(acr_cmd)
    if result["returncode"] == 0:
        logging.info(f"Successfully logged into ACR: {args.name}")
    else:
        logging.error(result["err_msg"])
        raise AzureError(result["err_msg"])

    # Get the repositories in the ACR
    logging.info(f"Fetching repositories in: {args.name}")
    list_cmd = ["az", "acr", "repository", "list", "-n", args.name, "-o", "tsv"]

    result = run_cmd(list_cmd)
    if result["returncode"] == 0:
        logging.info(f"Successfully fetched repositories from: {args.name}")
        repos = result["output"].split("\n")[:-1]
        logging.info(f"Total number of repositories: {len(repos)}")
    else:
        logging.error(result["err_msg"])
        raise AzureError(result["err_msg"])

    # Loop over the repositories
    logging.info("Checking repository manifests")
    for repo in repos:
        # Get the manifest for the current repository
        show_cmd = [
            "az", "acr", "repository", "show-manifests", "-n",
            args.name, "--repository", repo, "--orderby", "time_desc"
        ]

        result = run_cmd(show_cmd)
        if result["returncode"] == 0:
            logging.info(f"Successfully pulled manifests for: {repo}")
            outputs = result["output"].replace("\n", "").replace(" ", "")[1:-1].split("},")
            logging.info(f"Total number of manifests in {repo}: {len(outputs)}")
        else:
            logging.error(result["err_msg"])
            raise AzureError(result["err_msg"])

        # Loop over the manifests for each repository
        for j, output in enumerate(outputs):
            if j < (len(outputs) - 1):
                output += "}"

            # Convert the manifest to a dict and extract timestamp
            manifest = json.loads(output)
            timestamp = pd.to_datetime(manifest["timestamp"]).tz_localize(None)

            # Get time difference between now and the manifest timestamp
            diff = (pd.Timestamp.now() - timestamp).days

            # If an image is 90 days old or more, delete it
            if diff >= 90:
                logging.info(f"{repo}@{manifest['digest']} is {diff} days old.")
                images_to_be_deleted_digest.append(f"{repo}@{manifest['digest']}")
                images_to_be_deleted_number += 1

    if args.dry_run:
        logging.info(f"Number of images eligible for deletion: {images_to_be_deleted_number}")
    else:
        logging.info(f"Number of images to be deleted: {images_to_be_deleted_number}")

        for image in images_to_be_deleted_digest:
            logging.info(f"Deleting image: {image}")
            del_cmd = [
                "az", "acr", "repository", "delete", "-n", args.name,
                "--image", image
            ]

            result = run_cmd(del_cmd)
            if result["returncode"] == 0:
                logging.info(f"Successfully deleted image: {image}")
                deleted_images_total += 1
            else:
                logging.error(result["err_msg"])
                raise AzureError(result["err_msg"])

        logging.info(f"Number of images deleted: {deleted_images_total}")

if __name__ == "__main__":
    main()
