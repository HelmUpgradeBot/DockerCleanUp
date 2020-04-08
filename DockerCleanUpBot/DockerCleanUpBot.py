import json
import logging

import pandas as pd

from .run_command import run_cmd
from .CustomExceptions import AzureError

# Set up logging config
logging.basicConfig(
    level=logging.DEBUG,
    filename="DockerCleanUpBot.log",
    filemode="a",
    format="[%(asctime)s %(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class DockerCleanUpBot:
    """Clean up unused Docker images"""

    def __init__(self, argsDict):
        """Constructor function for DockerCleanUpBot class"""
        for k, v in argsDict.items():
            setattr(self, k, v)

        self.aggressive = None
        self.size = None

    def clean_up(self):
        """Perform image deletion"""
        if self.dry_run:
            logging.info("THIS IS A DRY RUN. NO IMAGES WILL BE DELETED.")
        if self.purge:
            logging.info("ALL IMAGES WILL BE PURGED")

        self.login()
        self.check_acr_size()
        image_df = self.check_manifests()

        if self.purge or self.aggressive:
            self.purge_all(image_df, dry_run=self.dry_run)

        else:
            if self.ci is not None:
                image_df = self.delete_ci_images(
                    image_df, self.ci, dry_run=self.dry_run
                )

            image_df = self.sort_and_delete(image_df, dry_run=self.dry_run)

        self.check_acr_size()
        logging.info("PROGRAM EXITING")

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

        if self.size < (self.limit * 1000.0):
            logging.info(
                "%s size is LESS THAN %.2f TB" % (self.name, self.limit)
            )
            self.aggressive = False
        else:
            logging.info(
                "%s size is LARGER THAN: %.2f TB" % (self.name, self.limit)
            )
            self.aggressive = True

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
            logging.info("Pulling manifests for: %s" % repo)
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

            logging.info("Successfully pulled manifests")
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

    def delete_ci_images(self, df, ci_repos, dry_run=False):
        """Delete images that were created by Continuous Integration tests"""
        if not dry_run:
            logging.info("Deleting repos generated by CI")

            for ci_string in ci_repos:
                for image in df["image_name"]:
                    if ci_string in image:
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

                        logging.info("Successfully deleted image")

                        df.drop(image, inplace=True)

        return df

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
        logging.info("Login to ACR: %s" % self.name)
        acr_cmd = ["az", "acr", "login", "-n", self.name]

        result = run_cmd(acr_cmd)

        if "login succeeded" in result["output"].lower():
            logging.info("Successfully logged into ACR")
        else:
            logging.error(result["err_msg"])
            raise AzureError(result["err_msg"])

    def purge_all(self, df, dry_run=True):
        """Purges all images in a Container Registry

        Arguments:
            df {pd.DataFrame} -- DataFrame containing info about the images in
                                 the container registry

        Keyword Arguments:
            dry_run {bool} -- Whether images should be deleted (default: {True})
        """
        if not dry_run:
            for image in df["image_name"]:
                logging.info("Deleting image: % s" % image)

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

                logging.info("Image successfully deleted")

    def sort_and_delete(self, image_df, dry_run=True):
        """Sorts images by age and deletes the oldest ones

        Arguments:
            image_df {pd.DataFrame} -- DataFrame containing info on the images
                                       in the Container Regsitry
        """
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

                logging.info("Successfully deleted image: %s" % image)
                image_df.drop(image, inplace=True)
                freed_up_space += old_image_df["size_gb"].loc[
                    old_image_df["image_name"] == image
                ]

            logging.info(
                "Space saved by deleting images: %d GB" % freed_up_space
            )

        image_df.reset_index(drop=True, inplace=True)
        return image_df
