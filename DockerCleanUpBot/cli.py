import sys
import argparse

from .DockerCleanUpBot import DockerCleanUpBot

DESCRIPTION = (
    "Script to clean old Docker images out of an Azure Container Registry"
)
parser = argparse.ArgumentParser(description=DESCRIPTION)

parser.add_argument(
    "name", type=str, help="Name of Azure Container Registry to clean"
)

parser.add_argument(
    "-a",
    "--max-age",
    type=int,
    default=90,
    help="Maximum age of images in days, older images will be deleted. Default: 90 days.",
)
parser.add_argument(
    "-l",
    "--limit",
    type=float,
    default=2.0,
    help="Maximum size in TB the ACR is allowed to grow to. Default: 2 TB.",
)
parser.add_argument(
    "--ci",
    nargs="+",
    default=None,
    help="List of images built by CI to be deleted",
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


def main():
    """Main function"""
    args = parser.parse_args(sys.argv[1:])
    obj = DockerCleanUpBot(vars(args))
    obj.clean_up()


if __name__ == "__main__":
    main()
