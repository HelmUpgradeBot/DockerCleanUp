import json
import logging
from .helper_functions import run_cmd

logger = logging.getLogger()


def check_acr_size(name: str, limit: float):
    """Check the size of an Azure Container Registry against a user-defined
    limit

    Args:
        name (str): The name of the ACR to be checked
        limit (float): The user-defined size limit of the ACR

    Returns:
        size (float): The size of the ACR in GB
        aggressive (bool): Aggressively clean the registry of large images
    """
    logger.info("Checking the size of ACR: %s" % name)

    size_cmd = ["az", "acr", "show-usage", "-n", name, "--query", "{}".format("value[?name=='Size'].currentValue"), "-o", "tsv"]
    result = run_cmd(size_cmd)

    if result["returncode"] != 0:
        logging.error(result["err_msg"])
        raise RuntimeError(result["err_msg"])

    size = int(result["output"]) * 1.0e-9
    logger.info("Size of %s: %.2f GB" % (name, size))

    if size < (limit * 1.0e3):
        logger.info("%s is LESS THAN %.2f TB" % (name, limit))
        aggressive = False
    elif size >= (limit * 1.0e3):
        logger.info("%s is LARGER THAN %.2f TB" % (name, limit))
        aggressive = True
    else:
        raise ValueError()

    return size, aggressive

