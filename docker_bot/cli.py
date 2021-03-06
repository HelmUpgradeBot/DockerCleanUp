import sys
import logging
import argparse
from .app import run
from multiprocessing import cpu_count


def logging_config(verbose: bool = False) -> None:
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="[%(asctime)s %(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        logging.basicConfig(
            level=logging.DEBUG,
            filename="docker-bot.log",
            filemode="a",
            format="[%(asctime)s %(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def parse_args(args):
    DESCRIPTION = "Script to clean old Docker images out of an Azure Container Registry (ACR)"
    parser = argparse.ArgumentParser(description=DESCRIPTION)

    parser.add_argument("name", type=str, help="Name of ACR to clean")

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
        "-t",
        "--threads",
        type=int,
        default=1,
        help="Number of threads to parallelise over",
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
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Purge all repositories within the ACR",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Output logs to console",
    )

    return parser.parse_args()


def check_parser(args):
    if args.dry_run and args.purge:
        raise ValueError("purge and dry-run options cannot be used together")

    if args.threads != 1:
        cpus = cpu_count()
        if args.threads > cpus:
            raise ValueError(
                "You have requested more threads than are available cores on this machine.\n"
                f"This machine has {cpus} CPUs available.\n"
                "Please adjust the value of --threads accordingly."
            )


def main():
    """Main function"""
    args = parse_args(sys.argv[1:])
    check_parser(args)

    logging_config(args.verbose)

    run(
        args.name,
        args.max_age,
        args.limit,
        args.threads,
        dry_run=args.dry_run,
        purge=args.purge,
        identity=args.identity,
    )


if __name__ == "__main__":
    main()
