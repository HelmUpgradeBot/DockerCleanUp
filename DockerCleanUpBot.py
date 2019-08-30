import os
import json
import logging
import argparse
import pandas as pd
from CustomExceptions import *
from run_command import run_cmd

# Set up logging config
logging.basicConfig(
    level=logging.DEBUG,
    filename="DockerCleanUpBot_{}.log".format(
        pd.Timestamp.today().strftime("%Y%m%d_%H%M%S")
    ),
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
        "-a",
        "--max-age",
        type=int,
        default=90,
        help="Maximum age of images, older images will be deleted."
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=float,
        default=2,
        help="Maximum size the ACR is allowed to grow to in TB"
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

class DockerCleanUpBot(object):
    def __init__(self, argsDict):
        self.images_to_be_deleted_number = 0
        self.images_to_be_deleted_digest = []
        self.deleted_images_total = 0

        # Parse arguments
        self.name = argsDict["name"]
        self.max_age = argsDict["max_age"]
        self.limit = argsDict["limit"]
        self.identity = argsDict["identity"]
        self.dry_run = argsDict["dry_run"]

    def clean_up(self):
        if self.dry_run:
            logging.info("THIS IS A DRY RUN. NO IMAGES WILL BE DELETED.")

        self.login()
        self.check_acr_size()

        if self.size < (self.limit * 1000.0):
            logging.info(f"{self.name} size is LESS THAN: {self.limit:.2f} TB. Performing STANDARD clean up operations.")
            self.aggressive = False
        else:
            logging.info(f"{self.name} size is LARGER THAN: {self.limit:.2f} TB. Performing AGGRESSIVE clean up operations.")
            self.aggressive = True
            self.max_age = 60

        repos = self.fetch_repos()

        if self.aggressive:
            logging.info("Performing AGGRESSIVE clean up")
            image_df = self.get_image_sizes(repos)
            self.sort_and_delete(image_df, dry_run=self.dry_run)

        self.check_manifests(repos)

        if self.dry_run:
            logging.info(f"Number of images eligible for deletion: {self.images_to_be_deleted_number}")
        else:
            logging.info(f"Number of images to be deleted: {self.images_to_be_deleted_number}")
            self.delete_images()

    def login(self):
        # Login to Azure
        login_cmd = ["az", "login"]

        if self.identity:
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
        acr_cmd = ["az", "acr", "login", "-n", self.name]

        result = run_cmd(acr_cmd)
        if result["returncode"] == 0:
            logging.info(f"Successfully logged into ACR: {self.name}")
        else:
            logging.error(result["err_msg"])
            raise AzureError(result["err_msg"])

    def check_acr_size(self):
        # Check the size of the ACR
        logging.info(f"Checking size of ACR: {self.name}")
        size_cmd = [
            "az", "acr", "show-usage", "-n", self.name, "--query",
            "{}".format("value[?name=='Size'].currentValue"), "-o", "tsv"
        ]

        result = run_cmd(size_cmd)
        if result["returncode"] == 0:
            self.size = int(result["output"]) * 1.0e-9
            logging.info(f"Size of {self.name}: {self.size:.2f} GB")
        else:
            logging.error(result["err_msg"])
            raise AzureError(result["err_msg"])

    def fetch_repos(self):
        # Get the repositories in the ACR
        logging.info(f"Fetching repositories in: {self.name}")
        list_cmd = [
            "az", "acr", "repository", "list", "-n", self.name, "-o", "tsv"
        ]

        result = run_cmd(list_cmd)
        if result["returncode"] == 0:
            logging.info(f"Successfully fetched repositories from: {self.name}")
            repos = result["output"].split("\n")[:-1]
            logging.info(f"Total number of repositories: {len(repos)}")
            return repos
        else:
            logging.error(result["err_msg"])
            raise AzureError(result["err_msg"])

    def check_manifests(self, repos):
        # Loop over the repositories
        logging.info("Checking repository manifests")
        for repo in repos:
            # Get the manifest for the current repository
            show_cmd = [
                "az", "acr", "repository", "show-manifests", "-n",
                self.name, "--repository", repo
            ]

            result = run_cmd(show_cmd)
            if result["returncode"] == 0:
                logging.info(f"Successfully pulled manifests for: {repo}")
                outputs = result["output"].replace(
                    "\n", "").replace(" ", "")[1:-1].split("},")
                logging.info(
                    f"Total number of manifests in {repo}: {len(outputs)}"
                )
            else:
                logging.error(result["err_msg"])
                raise AzureError(result["err_msg"])

            # Loop over the manifests for each repository
            for j, output in enumerate(outputs):
                if j < (len(outputs) - 1):
                    output += "}"

                # Convert the manifest to a dict and extract timestamp
                manifest = json.loads(output)
                timestamp = pd.to_datetime(
                    manifest["timestamp"]).tz_localize(None)

                # Get time difference between now and the manifest timestamp
                diff = (pd.Timestamp.now() - timestamp).days
                logging.info(f"{repo}@{manifest['digest']} is {diff} days old.")

                # If an image is too old, add it to delete list
                if diff >= self.max_age:
                    self.images_to_be_deleted_digest.append(
                        f"{repo}@{manifest['digest']}"
                    )
                    self.images_to_be_deleted_number += 1

    def delete_images(self):
        for image in self.images_to_be_deleted_digest:
            logging.info(f"Deleting image: {image}")
            del_cmd = [
                "az", "acr", "repository", "delete", "-n", self.name,
                "--image", image
            ]

            result = run_cmd(del_cmd)
            if result["returncode"] == 0:
                logging.info(f"Successfully deleted image: {image}")
                self.deleted_images_total += 1
            else:
                logging.error(result["err_msg"])
                raise AzureError(result["err_msg"])

        logging.info(f"Number of images deleted: {self.deleted_images_total}")

    def get_image_sizes(self, repos):
        logging.info("Collating image sizes")
        image_df = pd.DataFrame(columns=["image", "size"])
        image_number = 0

        # Loop over the repositories
        logging.info("Checking repository manifests")
        for repo in repos:
            # Get the manifest for the current repository
            show_cmd = [
                "az", "acr", "repository", "show-manifests", "-n",
                self.name, "--repository", repo
            ]

            result = run_cmd(show_cmd)
            if result["returncode"] == 0:
                logging.info(f"Successfully pulled manifests for: {repo}")
                outputs = result["output"].replace(
                    "\n", "").replace(" ", "")[1:-1].split("},")
                logging.info(
                    f"Total number of manifests in {repo}: {len(outputs)}"
                )
            else:
                logging.error(result["err_msg"])
                raise AzureError(result["err_msg"])

            # Loop over the manifests for each repository
            for j, output in enumerate(outputs):
                if j < (len(outputs) - 1):
                    output += "}"

                # Convert the manifest to a dict and extract timestamp
                manifest = json.loads(output)

                # Check the size of each image
                image_size_cmd = [
                    "az", "acr", "repository", "show", "-n", self.name,
                    "--image", f"{repo@manifest['digest']}", "--query",
                     "imageSize", "-o", "tsv"
                ]

                result = run_cmd(image_size_cmd)
                if result["returncode"] == 0:
                    image_size = int(result["output"]) * 1.0e-9
                    image_df.loc[image_number] = [
                        f"{repo@manifest['digest']}", image_size
                    ]
                    image_number += 1
                    logging.info(
                        f"Size of image {repo}@{manifest['digest']}: {image_size:.2f} GB"
                    )
                else:
                    logging.error(result["err_msg"])
                    raise AzureError(result["err_msg"])

        return image_df

    def sort_and_delete(self, image_df, number=25, dry_run=True):
        freed_up_space = 0

        logging.info("Sorting images by descending size")
        image_df.sort_values("size", ascending=False, inplace=True)
        image_df.reset_index(drop=True, inplace=True)

        if len(image_df) < number:
            number = len(image_df)

        for i, row in image_df.iterrows():
            if i < number:
                freed_up_space += row["size"]

                if not dry_run:
                    logging.info(f"Deleting image: {row['image']}")
                    delete_cmd = [
                        "az", "acr", "repository", "delete", "-n", self.name,
                        "--image", f"{row['image']}"
                    ]

                    result = run_cmd(delete_cmd)
                    if result["returncode"] == 0:
                        logging.info(
                            f"Successfully delete image: {row['image']}"
                        )
                    else:
                        logging.error(result["err_msg"])
                        raise AzureError(result["err_msg"])
            else:
                break

        logging.info(
            f"Space saved by deleting the {number} largest images: {freed_up_space} GB"
        )

if __name__ == "__main__":
    args = parse_args()
    bot = DockerCleanUpBot(vars(args))
    bot.clean_up()
