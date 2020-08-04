# DockerCleanUp

[![License](https://img.shields.io/github/license/HelmUpgradeBot/DockerCleanUp)](LICENSE) [![Code of Conduct](https://img.shields.io/badge/Code%20of-Conduct-blueviolet)](CODE_OF_CONDUCT.md) [![Contributing Guidelines](https://img.shields.io/badge/Contributing-Guidelines-blueviolet)](CONTRIBUTING.md) [![Good first issue](https://img.shields.io/github/labels/HelmUpgradeBot/DockerCleanUp/good%20first%20issue)](https://github.com/HelmUpgradeBot/DockerCleanUp/labels/good%20first%20issue) [![Help wanted](https://img.shields.io/github/labels/HelmUpgradeBot/DockerCleanUp/help%20wanted)](https://github.com/HelmUpgradeBot/DockerCleanUp/labels/help%20wanted)

This is an automatable bot to clean up Docker images stored in an [Azure Container Registry (ACR)](https://docs.microsoft.com/en-us/azure/container-registry/) that are 90 days old or more.
It also checks that the ACR hasn't grown above a certain memory limit.

| | :recycle: CI Status |
| :--- | :--- |
| Tests | [![Tests](https://github.com/HelmUpgradeBot/DockerCleanUp/workflows/Tests/badge.svg)](https://github.com/HelmUpgradeBot/DockerCleanUp/actions?query=workflow%3ATests) |
| Black | [![Black](https://github.com/HelmUpgradeBot/DockerCleanUp/workflows/Black/badge.svg)](https://github.com/HelmUpgradeBot/DockerCleanUp/actions?query=workflow%3ABlack) |
| Flake8 | [![Flake8](https://github.com/HelmUpgradeBot/DockerCleanUp/workflows/Flake8/badge.svg)](https://github.com/HelmUpgradeBot/DockerCleanUp/actions?query=workflow%3AFlake8) |

**Table of Contents:**

- [:mag: Overview](#mag-overview)
- [🤔 Assumptions DockerCleanUp Makes](#-assumptions-dockercleanupbot-makes)
- [:pushpin: Installation and Requirements](#pushpin-installation-and-requirements)
  - [:cloud: Installing Azure CLI](#cloud-installing-azure-cli-on-linux)
  - [:whale: Installing Docker CLI (on Linux)](#whale-installing-docker-cli-on-linux)
- [:children_crossing: Usage](#children_crossing-usage)
- [:clock2: CRON Expression](#clock2-cron-expression)
- [:white_check_mark: Running Tests](#white_check_mark-running-tests)
- [:leftwards_arrow_with_hook: Pre-commit Hook](#leftwards_arrow_with_hook-pre-commit-hook)
- [:sparkles: Contributing](#sparkles-contributing)

---

## :mag: Overview

This is an overview of the steps the bot executes.

- Logs into Azure using **either** a [Managed System Identity](https://docs.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/overview) **or** interactive login (configurable with a command line flag)
- Logs in to the requested ACR via the Azure command line interface and Docker daemon
- Checks the size of the ACR and compares it to a requested size limit (configurable with a command line flag)
- Fetches the repositories and manifests for the images in the ACR and saves them in a pandas dataframe
- Filters out image digests that are older than the requested age limit (configurable with a command line flag) and deletes them
- Rechecks the size of the ACR
  - If the ACR is still larger than the requested size limit, the bot then executes a loop to delete the largest remaining image until the ACR is below the size limit

## 🤔 Assumptions DockerCleanUpBot Makes

To login to Azure, the bot assumes it's being run from a resource (for example, a Virtual Machine) with a [Managed System Identity](https://docs.microsoft.com/en-gb/azure/active-directory/managed-identities-azure-resources/overview) that has enough permissions ([Reader and AcrDelete](https://docs.microsoft.com/en-us/azure/container-registry/container-registry-roles) at least) to access the ACR and delete images.

## :pushpin: Installation and Requirements

To install this bot, you'll need to clone this repo and install the package.
It requires Python version >=3.7.

```bash
git clone https://github.com/HelmUpgradeBot/DockerCleanUp.git
cd DockerCleanUp
python setup.py install
```

The bot will need access to the [Microsoft Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest) and the [Docker CLI](https://docs-stage.docker.com/v17.12/install/) in order to query the ACR.

### :cloud: Installing Azure CLI (on Linux)

To install the Azure command line interface, run the following:

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

See the [Microsoft Azure CLI Installation docs](https://docs.microsoft.com/en-gb/cli/azure/install-azure-cli?view=azure-cli-latest) for more installation options.

### :whale: Installing Docker CLI (on Linux)

To install the Docker command line interface, run the following:

```bash
sudo apt install docker.io -y
sudo usermod -a -G docker $USER
```

You will need to restart the terminal for the second command to take effect.

## :children_crossing: Usage

```bash
usage: docker-bot [-h] [-a MAX_AGE] [-l LIMIT] [-t THREADS] [--identity]
                  [--dry-run] [--purge] [-v]
                  name

Script to clean old Docker images out of an Azure Container Registry (ACR)

positional arguments:
  name                  Name of ACR to clean

optional arguments:
  -h, --help            show this help message and exit
  -a MAX_AGE, --max-age MAX_AGE
                        Maximum age of images in days, older images will be
                        deleted. Default: 90 days.
  -l LIMIT, --limit LIMIT
                        Maximum size in TB the ACR is allowed to grow to.
                        Default: 2 TB.
  -t THREADS, --threads THREADS
                        Number of threads to parallelise over
  --identity            Login to Azure with a Managed System Identity
  --dry-run             Do a dry-run, no images will be deleted.
  --purge               Purge all repositories within the ACR
  -v, --verbose         Output logs to console
```

## :clock2: CRON expression

To run this script at midnight on the first day of every month, use the following cron expression:

```bash
0 0 1 * * cd /path/to/DockerCleanUp && ~/path/to/python setup.py install &&DockerCleanUpBot.py [--flags]
```

## :white_check_mark: Running Tests

After following the [installation instructions](#pushpi-installation-and-requirements), the test suite can be run with the following command:

```bash
python -m pytest -vvv
```

To see the coverage of the test suite, execute the following:

```bash
python -m coverage run -m pytest -vvv

coverage report  # To have coverage printed to the terminal
coverage html    # To generate interactive html pages detailing the coverage
```

## :leftwards_arrow_with_hook: Pre-commit Hook

For developing the bot, a pre-commit hook can be installed which will apply [black](https://github.com/psf/black) and [flake8](http://flake8.pycqa.org/en/latest/) linters and formatters to the Python files.
To install the hook, run the following:

```bash
pip install -r dev-requirements.txt
pre-commit install
```

## :sparkles: Contributing

Thank you for your interest in contributing to the project! :tada:
Please read our [:purple_heart: Code of Conduct](CODE_OF_CONDUCT.md) and [:space_invader: Contributing Guidelines](CONTRIBUTING.md) to get you started.
