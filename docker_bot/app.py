import sys
import json
import logging
import datetime
import itertools
import pandas as pd
from typing import Tuple
from .helper_functions import run_cmd
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

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


def pull_image_age(acr_name: str, manifest: dict) -> Tuple[str, int]:
    """Get the age of an image in an Azure Container Registry

    Args:
        acr_name (str): Name of the ACR
        manifest (dict): Image manifest

    Returns:
        image_name (str): Name of the image -> repo@digest
        age_days (int): Age of the image in days
    """
    # Get the time difference between now and the manifest timestamp in days
    timestamp = pd.to_datetime(manifest["timestamp"]).tz_localize(None)
    diff = (datetime.datetime.now() - timestamp).days
    logger.info(
        "%s@%s is %d days old" % (manifest["repo"], manifest["digest"], diff)
    )

    return (
        f"{manifest['repo']}@{manifest['digest']}",
        diff,
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


def purge_all(acr_name: str, df: pd.DataFrame) -> None:
    """Purge all images from an Azure Container Registry

    Args:
        acr_name (str): The name of the ACR to purge
        df (pd.DataFrame): A DataFrame containing images stored in the ACR
    """
    for image_name in df.index:
        logger.info("Deleting image: %s" % image_name)

        delete_cmd = [
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

        result = run_cmd(delete_cmd)

        if result["returncode"] != 0:
            logger.erro(result["err_msg"])
            raise RuntimeError(result["err_msg"])


def run(
    acr_name: str,
    max_age: int,
    limit: float,
    threads: int,
    dry_run: bool = False,
    purge: bool = False,
    identity: bool = False,
) -> None:
    """Run the Docker Clean Up process

    Args:
        acr_name (str): The name of the ACR to clean
        max_age (int): The maximum image age in days
        limit (float): The maximum size limit of the ACR in TB
        threads (int): The number of threads to parallelise over
        dry_run (bool, optional): Don't delete any images from the ACR.
                                  Defaults to False.
        purge (bool, optional): Delete all images from the ACR.
                                Defaults to False.
        identity (bool, optional): Login to Azure with a Managed Identity.
                                   Defaults to False.
    """
    if dry_run:
        logger.info("THIS IS A DRY RUN. NO IMAGES WILL BE DELETED.")
    if purge:
        logger.info("ALL IMAGES WILL BE DELETED!")

    # Login to Azure and ACR
    login(identity=identity)

    # Check the size of the ACR
    size, proceed = check_acr_size(acr_name, limit)

    # If the ACR is too large or --purge was set, then when need to do stuff!
    if proceed or purge:
        # Get the repos in the ACR
        repos = pull_repos(acr_name)

        # Get the manifests for the repos in the ACR
        logger.info("Checking repository manifests")
        manifests = {}

        with ThreadPoolExecutor() as executor:
            # Schedule the first `threads` futures. We don't want to schedule
            # them all at once to avoid consuming excessive amounts of memory.
            futures = {
                executor.submit(pull_manifest, acr_name, repo): repo
                for repo in itertools.islice(repos, threads)
            }

            while futures:
                # Wait for the next future to complete
                done, _ = wait(futures, return_when=FIRST_COMPLETED)

                for fut in done:
                    cases = futures.pop(fut)
                    for case in cases.result():
                        manifests.update(item)

                # Schedule the next set of futures. We don't want more than
                # `threads` futures in the pool at a time to keep memory
                # consumption down.
                for repo in itertools.islice(repos, len(done)):
                    fut = executor.submit(pull_manifest, acr_name, repo)
                    futures[fut] = repo

        # Checking sizes of images
        logger.info("Checking image sizes")
        image_df = pd.DataFrame(columns=["image_name", "age_days"])

        with ThreadPoolExecutor() as executor:
            # Schedule the first `threads` futures. We don't want to schedule
            # them all at once, to avoid consuming excessive amounts of memory.
            futures = {
                executor.submit(pull_image_age, acr_name, manifest): manifest
                for manifest in itertools.islice(manifests, threads)
            }

            while futures:
                # Wait for the next future to complete
                done, _ = wait(futures, return_when=FIRST_COMPLETED)

                for fut in done:
                    output = futures.pop(fut)
                    image_name, age_days = future

                    image_df = image_df.append(
                        {"image_name": image_name, "age_days": age_days},
                        ignore_index=True,
                    )

                # Schedule the next set of futures. We don't want more than
                # `threads` futures in the pool at a time, to keep memory
                # consumption down.
                for manifest in itertools.islice(manifests, len(done)):
                    fut = executor.submit(pull_image_age, acr_name, manifest)
                    futures[fut] = manifest

        image_df.set_index("image_name", inplace=True)

        # If the ACR is under the size limit but purge has been set anyway,
        # purge the ACR and exit the program
        if purge and not proceed:
            logging.info("Purging ACR: %s" % acr_name)
            purge_all(acr_name, image_df)
            sys.exit(0)

        # If the ACR is above the size limit
        if proceed and not purge:
            # Find the oldest images to delete
            logger.info("Filtering dataframe for old images")
            images_to_delete = sort_image_df(image_df, max_age)

            if dry_run:
                logger.info(
                    "Number of images elegible for deletion %s"
                    % len(images_to_delete)
                )
            else:
                logger.info(
                    "Number of images to be deleted: %s"
                    % len(images_to_delete)
                )

                # Delete the old images
                for image_name in images_to_delete.index:
                    delete_image(acr_name, image_name)
                    image_df.drop(image_name, inplace=True)

            # Re-check ACR size
            size, proceed = check_acr_size(acr_name)

            if proceed:
                # Advise the user to re-run since the ACR is still large
                logger.info(
                    "Size of %s still LARGER THAN %s TB. Please re-run and optionally set the --purge flag."
                    % (acr_name, limit)
                )

    # The ACR is under the size limit and the --purge flag has not been set
    elif not proceed and not purge:
        logger.info("Nothing to do. PROGRAM EXITING.")
