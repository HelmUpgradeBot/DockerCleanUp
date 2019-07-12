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
import argparse
import pandas as pd
from subprocess import check_call, check_output

# Get environment variable
REGISTRY_NAME = os.environ.get("NAME")

class dockerCleanUpBot:
    def __init__(self):
        self.dry_run = True if args.dry_run is None else args.dry_run
        self.images_to_be_deleted_number = 0
        self.images_to_be_deleted_digest = []

    def cleanup(self):
        if self.dry_run:
            print("THIS IS A DRY RUN.  NO IMAGES WILL BE DELETED.")

        self.login_to_acr()
        REPOS = self.fetch_repos()
        self.check_manifests(REPOS)

        if self.dry_run:
            print(f"Number of images eligible for deletion: {self.images_to_be_deleted_number}")
        else:
            print(f"Number of images to be deleted: {self.images_to_be_deleted_number}")
            self.delete_images()

    def login_to_acr(self):
        print("--> Login to ACR")
        check_call(["az", "acr", "login", "-n", REGISTRY_NAME])

    def fetch_repos(self):
        print("--> Fetching repositories")
        # Get the repositories in the ACR
        output = check_output([
            "az", "acr", "repository", "list", "-n", REGISTRY_NAME, "-o", "tsv"
        ]).decode()
        REPOS = output.split("\n")[:-1]

        return REPOS

    def check_manifests(self, REPOS):
        # Loop over the repositories
        for REPO in REPOS:
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

                # Get time difference between now and the manifest timestamp
                diff = (pd.Timestamp.now() - timestamp).days

                # If an image is 90 days old or more, delete it
                if diff >= 90:
                    self.images_to_be_deleted_digest.append(f"{REPO}@{MAINFEST['digest']}")
                    self.images_to_be_deleted_number += 1

    def delete_images(self):
        for image in self.images_to_be_deleted_digest:
            print(f"--> Deleting image: {image}")
            check_call([
                "az", "acr", "repository", "delete", "-n", REGISTRY_NAME,
                "--image", f"{image}"
            ])

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do a dry-run, no images will be deleted."
    )

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    bot = dockerCleanUpBot()
    bot.cleanup()
