"""
Script to clean old Docker images out of an Azure Container Registry
"""
import json
import logging
import argparse
import pandas as pd
from CustomExceptions import AzureError
from run_command import run_cmd

# Set up logging config
logging.basicConfig(
    level=logging.DEBUG,
    filename="DockerCleanUpBot.log",
    filemode="a",
    format="[%(asctime)s %(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def parse_args():
    """Parse command line arguments and return them"""
    parser = argparse.ArgumentParser(
        description="Script to clean old Docker images out of an Azure Container Registry"
    )

    parser.add_argument(
        "-n",
        "--name",
        type=str,
        required=True,
        help="Name of Azure Container Registry to clean",
    )
    parser.add_argument(
        "-a",
        "--max-age",
        type=int,
        default=90,
        help="Maximum age of images, older images will be deleted.",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=float,
        default=2,
        help="Maximum size the ACR is allowed to grow to in TB",
    )
    parser.add_argument(
        "--identity",
        action="store_true",
        help="Login to Azure with a Managed System Identity",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do a dry-run, no images will be deleted.",
    )

    return parser.parse_args()


class DockerCleanUpBot:
    """Clean up unused Docker images"""

    def __init__(self, argsDict):
        self.images_to_be_deleted_number = 0
        self.images_to_be_deleted_digest = []
        self.deleted_images_total = 0
        self.aggressive = None
        self.size = None

        # Parse arguments
        self.name = argsDict["name"]
        self.max_age = argsDict["max_age"]
        self.limit = argsDict["limit"]
        self.identity = argsDict["identity"]
        self.dry_run = argsDict["dry_run"]

    def clean_up(self):
        """Perform image deletion"""
        if self.dry_run:
            logging.info("THIS IS A DRY RUN. NO IMAGES WILL BE DELETED.")

        self.login()
        self.check_acr_size()

        if self.size < (self.limit * 1000.0):
            logging.info(
                "%s size is LESS THAN: %.2f TB. Performing STANDARD clean up operations."
                % (self.name, self.limit)
            )
            self.aggressive = False
        else:
            logging.info(
                "%s size is LARGER THAN: %.2f TB. Performing AGGRESSIVE clean up operations."
                % (self.name, self.limit)
            )
            self.aggressive = True
            self.max_age = 60

        repos = self.fetch_repos()

        if self.aggressive:
            logging.info("Performing AGGRESSIVE clean up")
            image_df = self.get_image_sizes(repos)
            self.sort_and_delete(image_df, dry_run=self.dry_run)

        self.check_manifests(repos)

        if self.dry_run:
            logging.info(
                "Number of images eligible for deletion: %d"
                % self.images_to_be_deleted_number
            )
        else:
            logging.info(
                "Number of images to be deleted: %d"
                % self.images_to_be_deleted_number
            )
            self.delete_images()

    def login(self):
        """Login to Azure and the ACR"""
        # Login to Azure
        login_cmd = ["az", "login"]

        if self.identity:
            login_cmd.append("--identity")
            logging.info("Login to Azure with Managed System Identity")
        else:
            logging.info("Login to Azure")

        result = run_cmd(login_cmd)

        if result["returncode"] != 0:
            logging.error(result["err_msg"])
            raise AzureError(result["err_msg"])

        logging.info("Successfully logged into Azure")

        # Login to ACR
        logging.info("Login to ACR")
        acr_cmd = ["az", "acr", "login", "-n", self.name]

        result = run_cmd(acr_cmd)

        if result["returncode"] != 0:
            logging.error(result["err_msg"])
            raise AzureError(result["err_msg"])

        logging.info("Successfully logged into ACR: %s" % self.name)

    def check_acr_size(self):
        """Check the size of the ACR"""
        logging.info("Checking size of ACR: %s" % self.name)
        size_cmd = [
            "az",
            "acr",
            "show-usage",
            "-n",
            self.name,
            "--query",
            "{}".format("value[?name=='Size'].currentValue"),
            "-o",
            "tsv",
        ]

        result = run_cmd(size_cmd)

        if result["returncode"] != 0:
            logging.error(result["err_msg"])
            raise AzureError(result["err_msg"])

        self.size = int(result["output"]) * 1.0e-9
        logging.info("Size of %s: %.2f GB" % (self.name, self.size))

    def fetch_repos(self):
        """Get the repositories in the ACR"""
        logging.info("Fetching repositories in: %s" % self.name)
        list_cmd = [
            "az",
            "acr",
            "repository",
            "list",
            "-n",
            self.name,
            "-o",
            "tsv",
        ]

        result = run_cmd(list_cmd)

        if result["returncode"] != 0:
            logging.error(result["err_msg"])
            raise AzureError(result["err_msg"])

        logging.info("Successfully fetched repositories from: %s" % self.name)
        repos = result["output"].split("\n")[:-1]
        logging.info("Total number of repositories: %d" % len(repos))
        return repos

    def check_manifests(self, repos):
        """Check the manifests for each image in the repository"""
        # Loop over the repositories
        logging.info("Checking repository manifests")
        for repo in repos:
            # Get the manifest for the current repository
            show_cmd = [
                "az",
                "acr",
                "repository",
                "show-manifests",
                "-n",
                self.name,
                "--repository",
                repo,
            ]

            result = run_cmd(show_cmd)

            if result["returncode"] != 0:
                logging.error(result["err_msg"])
                raise AzureError(result["err_msg"])

            logging.info("Successfully pulled manifests for: %s" % repo)
            outputs = (
                result["output"]
                .replace("\n", "")
                .replace(" ", "")[1:-1]
                .split("},")
            )
            logging.info(
                "Total number of manifests in %s: %d" % (repo, len(outputs))
            )

            # Loop over the manifests for each repository
            for j, output in enumerate(outputs):
                if j < (len(outputs) - 1):
                    output += "}"

                # Convert the manifest to a dict and extract timestamp
                manifest = json.loads(output)
                timestamp = pd.to_datetime(manifest["timestamp"]).tz_localize(
                    None
                )

                # Get time difference between now and the manifest timestamp
                diff = (pd.Timestamp.now() - timestamp).days
                logging.info(
                    "%s@%s is %d days old." % (repo, manifest["digest"], diff)
                )

                # If an image is too old, add it to delete list
                if diff >= self.max_age:
                    self.images_to_be_deleted_digest.append(
                        "%s@%s" % (repo, manifest["digest"])
                    )
                    self.images_to_be_deleted_number += 1

    def delete_images(self):
        """Perform image deletion"""
        for image in self.images_to_be_deleted_digest:
            logging.info("Deleting image: %s" % image)
            del_cmd = [
                "az",
                "acr",
                "repository",
                "delete",
                "-n",
                self.name,
                "--image",
                image,
                "--yes",
            ]

            result = run_cmd(del_cmd)

            if result["returncode"] != 0:
                logging.error(result["err_msg"])
                raise AzureError(result["err_msg"])

            logging.info("Successfully deleted image: %s" % image)
            self.deleted_images_total += 1

        logging.info(
            "Number of images deleted: %d" % self.deleted_images_total
        )

    def get_image_sizes(self, repos):
        """Get a dataframe with the sizes of all Docker images"""
        logging.info("Collating image sizes")
        image_df = pd.DataFrame(columns=["image", "size"])
        image_number = 0

        # Loop over the repositories
        logging.info("Checking repository manifests")
        for repo in repos:
            # Get the manifest for the current repository
            show_cmd = [
                "az",
                "acr",
                "repository",
                "show-manifests",
                "-n",
                self.name,
                "--repository",
                repo,
            ]

            result = run_cmd(show_cmd)

            if result["returncode"] != 0:
                logging.error(result["err_msg"])
                raise AzureError(result["err_msg"])

            logging.info("Successfully pulled manifests for: %s" % repo)
            outputs = (
                result["output"]
                .replace("\n", "")
                .replace(" ", "")[1:-1]
                .split("},")
            )
            logging.info(
                "Total number of manifests in %s: %d" % (repo, len(outputs))
            )

            # Loop over the manifests for each repository
            for j, output in enumerate(outputs):
                if j < (len(outputs) - 1):
                    output += "}"

                # Convert the manifest to a dict and extract timestamp
                manifest = json.loads(output)

                # Check the size of each image
                image_size_cmd = [
                    "az",
                    "acr",
                    "repository",
                    "show",
                    "-n",
                    self.name,
                    "--image",
                    f"{repo}@{manifest['digest']}",
                    "--query",
                    "imageSize",
                    "-o",
                    "tsv",
                ]

                result = run_cmd(image_size_cmd)

                if result["returncode"] != 0:
                    logging.error(result["err_msg"])
                    raise AzureError(result["err_msg"])

                image_size = int(result["output"]) * 1.0e-9
                image_df.loc[image_number] = [
                    f"{repo}@{manifest['digest']}",
                    image_size,
                ]
                image_number += 1
                logging.info(
                    "Size of image %s@%s: %.2f GB"
                    % (repo, manifest["digest"], image_size)
                )

        return image_df

    def sort_and_delete(self, image_df, number=25, dry_run=True):
        """Sort images and delete them"""
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
                    logging.info("Deleting image: %s" % row["image"])
                    delete_cmd = [
                        "az",
                        "acr",
                        "repository",
                        "delete",
                        "-n",
                        self.name,
                        "--image",
                        f"{row['image']}",
                        "--yes",
                    ]

                    result = run_cmd(delete_cmd)

                    if result["returncode"] != 0:
                        logging.error(result["err_msg"])
                        raise AzureError(result["err_msg"])

                    logging.info(
                        "Successfully delete image: %s" % row["image"]
                    )
            else:
                break

        logging.info(
            "Space saved by deleting the %d largest images: %d GB"
            % (number, freed_up_space)
        )


def main():
    """Main function"""
    args = parse_args()
    bot = DockerCleanUpBot(vars(args))
    bot.clean_up()


if __name__ == "__main__":
    main()
