import json
import logging
import datetime
import pandas as pd
from typing import Tuple
from .helper_functions import run_cmd

logger = logging.getLogger()


def login(acr_name: str, identity: bool = False) -> None:
    """Login to Azure and the specified Container Registry

    Args:
        acr_name (str): The ACR to be accessed
        identity (bool, optional): Login to Azure using a Managed Identity.
                                   Defaults to False.
    """
    # Login to Azure
    login_cmd = ["az", "login"]

    if identity:
        login_cmd.append("--identity")
        logger.info("Loggin into Azure with Managed Identity")
    else:
        logger.info("Logging into Azure interactively")

    result = run_cmd(login_cmd)

    if result["returncode"] != 0:
        logger.error(result["err_msg"])
        raise RuntimeError(result["err_msg"])

    logger.info("Successfully logged into Azure")

    # Login to ACR
    logger.info("Logging into ACR: %s" % acr_name)
    acr_cmd = ["az", "acr", "login", "-n", acr_name]

    result = run_cmd(acr_cmd)

    if "login succeeded" in result["output"].lower():
        logger.info("Successfully logged into ACR")
    else:
        logger.error(result["returncode"])
        raise RuntimeError(result["err_msg"])


def check_acr_size(acr_name: str, limit: float) -> Tuple[float, bool]:
    """Check the size of an Azure Container Registry against a user-defined
    limit

    Args:
        acr_name (str): The name of the ACR to be checked
        limit (float): The user-defined size limit of the ACR in TB

    Returns:
        size (float): The size of the ACR in GB
        proceed (bool): Proceed with image deletion if True
    """
    logger.info("Checking the size of ACR: %s" % acr_name)

    size_cmd = [
        "az",
        "acr",
        "show-usage",
        "-n",
        acr_name,
        "--query",
        "{}".format("value[?name=='Size'].currentValue"),
        "-o",
        "tsv",
    ]
    result = run_cmd(size_cmd)

    if result["returncode"] != 0:
        logging.error(result["err_msg"])
        raise RuntimeError(result["err_msg"])

    size = int(result["output"]) * 1.0e-9
    logger.info("Size of %s: %.2f GB" % (acr_name, size))

    if size < (limit * 1.0e3):
        logger.info("%s is LESS THAN %.2f TB" % (acr_name, limit))
        proceed = False
    elif size >= (limit * 1.0e3):
        logger.info("%s is LARGER THAN %.2f TB" % (acr_name, limit))
        proceed = True

    return size, proceed


def pull_repos(acr_name: str) -> list:
    """Pull list of repositories stored in an Azure Container Registry

    Args:
        acr_name (str): Name of the ACR

    Returns:
        list: All the repositories stored in the ACR
    """
    logger.info("Pulling repositories in: %s" % acr_name)
    list_cmd = ["az", "acr", "repository", "list", "-n", acr_name, "-o", "tsv"]

    result = run_cmd(list_cmd)

    if result["returncode"] != 0:
        logger.error(result["err_msg"])
        raise RuntimeError(result["err_msg"])

    logger.info("Successfully pulled repositories")
    repos = result["output"].split("\n")
    logger.info("Total number of repositories: %s" % len(repos))

    return repos


def pull_manifests(acr_name: str, repo: str) -> dict:
    """Return image manifests for a repository in an Azure Container Registry

    Args:
        acr_name (str): Name of the ACR
        repo (str): Name of the repository

    Returns:
        dict: The image manifests
    """
    logger.info("Pulling manifests for: %s" % repo)
    show_cmd = [
        "az",
        "acr",
        "repository",
        "show-manifests",
        "-n",
        acr_name,
        "--repository",
        repo,
    ]

    result = run_cmd(show_cmd)

    if result["returncode"] != 0:
        logger.error(result["err_msg"])
        raise RuntimeError(result["err_msg"])

    logging.info("Successfully pulled mainfests")
    manifests = json.loads(result["output"])
    print(manifests)
    logger.info("Total number of manifests in %s: %d" % (repo, len(manifests)))

    for manifest in manifests:
        manifest["repo"] = repo

    return manifests


def pull_image_size(acr_name: str, manifest: dict) -> Tuple[str, int, float]:
    """Get the size of an image in an Azure Container Registry

    Args:
        acr_name (str): Name of the ACR
        manifest (dict): Image manifest

    Returns:
        image_name (str): Name of the image -> repo@digest
        age_days (int): Age of the image in days
        size_gb (float): Size of the image in GB
    """
    # Get the time difference between now and the manifest timestamp in days
    timestamp = pd.to_datetime(manifest["timestamp"]).tz_localize(None)
    diff = (datetime.datetime.now() - timestamp).days
    logger.info(
        "%s@%s is %d days old" % (manifest["repo"], manifest["digest"], diff)
    )

    # Check the size of the image
    image_size_cmd = [
        "az",
        "acr",
        "repository",
        "show",
        "-n",
        acr_name,
        "--imag",
        f"{manifest['repo']}@{manifest['digest']}",
        "--query",
        "imageSize",
        "-o",
        "tsv",
    ]

    result = run_cmd(image_size_cmd)

    if result["returncode"] != 0:
        logger.error(result["err_msg"])
        raise RuntimeError(result["err_msg"])

    return (
        f"{manifest['repo']}@{manifest['digest']}",
        diff,
        int(result["output"]) * 1.0e-9,
    )


def sort_image_df(image_df: pd.DataFrame, max_age: int) -> pd.DataFrame:
    """Sort and reduce a DataFrame of Container image information to those that
    exceed a user-defined maximum age

    Args:
        image_df (pd.DataFrame): DataFrame containing information relating to
                                 the stored images
        max_age (int): The maximum age in days that the user stores the images for

    Returns:
        pd.DataFrame: DataFrame containing information for only the images that
                      exceed the maximum age limit
    """
    # Filter images by age
    image_df = image_df.loc[image_df["age_days"] >= max_age]
    return image_df.reset_index(drop=True)


def delete_image(acr_name: str, image_name: str) -> None:
    """Delete an image in an Azure Container Regsitry

    Args:
        acr_name (str): Name of the ACR
        image_name (str): Image to be deleted
    """
    logger.info("Deleting image: %s" % image_name)

    del_cmd = [
        "az",
        "acr",
        "repository",
        "delete",
        "-n",
        acr_name,
        "--image",
        image_name,
        "--yes",
    ]

    result = run_cmd(del_cmd)

    if result["returncode"] != 0:
        logger.error(result["err_msg"])
        raise RuntimeError(result["err_msg"])

    logger.info("Successfully deleted image")


def run(
    acr_name: str,
    max_age: int,
    limit: float,
    dry_run: bool = False,
    purge: bool = False,
    identity: bool = False,
) -> None:
    if dry_run:
        logger.info("THIS IS A DRY RUN. NO IMAGES WILL BE DELETED.")
    if purge:
        logger.info("ALL IMAGES WILL BE DELETED!")

    login(identity=identity)

    size, proceed = check_acr_size(acr_name, limit)

    if proceed or purge:
        repos = pull_repos(acr_name)

        logger.info("Checking repository manifests")
        manifests = {}
        for repo in repos:
            cases = pull_manifests(acr_name, repo)
            for case in cases:
                manifests.update(case)

        logger.info("Checking image sizes")
        image_df = pd.DataFrame(columns=["image_name", "age_days", "size_gb"])
        for manifest in manifests:
            image_name, age_days, image_size = pull_image_size(
                acr_name, manifest
            )
            image_df = image_df.append(
                {
                    "image_name": image_name,
                    "age_days": age_days,
                    "size_gb": image_size,
                },
                ignore_index=True,
            )

        if proceed and not purge:

            logger.info("Filtering dataframe for old images")
            images_to_delete = sort_image_df(image_df, max_age)

            if dry_run:
                logger.info("Number of images elegible for deletion %s" % len(images_to_delete))
            else:
                logger.info("Number of images to be deleted: %s" % len(images_to_delete))

                for image_name in images_to_delete.image_name:
                    delete_image(acr_name, image_name)
