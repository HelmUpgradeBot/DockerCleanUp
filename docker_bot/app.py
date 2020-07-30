import json
import logging
import pandas as pd
from typing import Tuple
from .helper_functions import run_cmd

logger = logging.getLogger()


def check_acr_size(acr_name: str, limit: float) -> Tuple[float, bool]:
    """Check the size of an Azure Container Registry against a user-defined
    limit

    Args:
        acr_name (str): The name of the ACR to be checked
        limit (float): The user-defined size limit of the ACR in TB

    Returns:
        size (float): The size of the ACR in GB
        aggressive (bool): Aggressively clean the registry of large images
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
        aggressive = False
    elif size >= (limit * 1.0e3):
        logger.info("%s is LARGER THAN %.2f TB" % (acr_name, limit))
        aggressive = True

    return size, aggressive


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
    logger.info("Total number of manifests in %s: %d" % (repo, len(manifests)))

    return manifests
