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
        help="Maximum age of images in days, older images will be deleted.",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=float,
        default=2,
        help="Maximum size in TB the ACR is allowed to grow to",
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
        self.number_images_deleted = 0
        self.aggressive = None
        self.size = None

        # Parse arguments
        for k, v in argsDict.items():
            setattr(self, k, v)

    def clean_up(self):
        """Perform image deletion"""
        if self.dry_run:
            logging.info("THIS IS A DRY RUN. NO IMAGES WILL BE DELETED.")

        self.login()
        self.check_acr_size()

        if self.size < (self.limit * 1000.0):
            logging.info(
                "%s size is LESS THAN %.2f TB." % (self.name, self.limit)
            )
            self.aggressive = False
        else:
            logging.info(
                "%s size is LARGER THAN: %.2f TB." % (self.name, self.limit)
            )
            self.aggressive = True

        image_df = self.check_manifests()

        self.sort_and_delete(image_df, dry_run=self.dry_run)

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

    def check_manifests(self):
        """Check the manifests for each image in the repository"""
        # Fetch image repositories
        repos = self.fetch_repos()

        # Create an empty dataframe
        df = pd.DataFrame(columns=["image_name", "age_days", "size_gb"])

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

                # Append to dataframe
                df = df.append(
                    {
                        "image_name": f"{repo}@{manifest['digest']}",
                        "age_days": diff,
                        "size_gb": image_size,
                    },
                    ignore_index=True,
                )

        return df

    def sort_and_delete(self, image_df, dry_run=True):
        """Sort images and delete them"""
        freed_up_space = 0

        # Filtering images by age
        logging.info("Filtering images by age")
        old_image_df = image_df.loc[image_df["age_days"] >= self.max_age]

        if dry_run:
            logging.info(
                "Number of images eligible for deletion: %d"
                % len(old_image_df)
            )
        else:
            logging.info(
                "Number of images to be deleted: %d" % len(old_image_df)
            )

            for image in old_image_df["image_name"]:
                logging.info("Deleting image: %s" % image)
                delete_cmd = [
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

                result = run_cmd(delete_cmd)

                if result["returncode"] != 0:
                    logging.error(result["err_msg"])
                    raise AzureError(result["err_msg"])

                logging.info("Successfully delete image: %s" % image)

                freed_up_space += old_image_df["size_gb"].loc[
                    old_image_df["image_name"] == image
                ]

            logging.info(
                "Space saved by deleting images: %d GB" % freed_up_space
            )


def main():
    """Main function"""
    args = parse_args()
    bot = DockerCleanUpBot(vars(args))
    bot.clean_up()


if __name__ == "__main__":
    main()
