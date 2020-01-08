# DockerCleanUp

This is an automatable bot to clean up Docker images stored in an Azure Container Registry (ACR) that are 90 days old or more.
It also checks that the ACR hasn't grown above a certain memory limit.

- [Overview](#overview)
- [Assumptions DockerCleanUp Makes](#assumptions-dockercleanupbot-makes)
- [Requirements](#requirements)
  - [Installing Azure CLI](#installing-azure-cli)
  - [Installing Docker CLI (on Linux)](#installing-docker-cli-on-linux)
- [Usage](#usage)
- [CRON Expression](#cron-expression)
- [Pre-commit Hook](#pre-commit-hook)

---

## Overview

This is an overview of the steps the bot executes.

- Logs in to Azure using **either** a Managed System Identity **or** interactive login (configurable with a command line flag)
- Logs in to the requested ACR via the Azure CLI and Docker daemon
- Checks the size of the ACR and compares it to a requested size limit (configurable with a command line flag)
- Fetches the repositories and manifests for the images in the ACR and saves them in a pandas dataframe
- Filters out image digests that are older than the requested age limit (configurable with a command line flag) and deletes them
- Rechecks the size of the ACR
  - If the ACR is still larger than the requested size limit, the bot then executes a loop to delete the largest remaining image until the ACR is below the size limit

## Assumptions DockerCleanUpBot Makes

To login to Azure, the bot assumes it's being run from a resource (for example, a Virtual Machine) with a [Managed System Identity](https://docs.microsoft.com/en-gb/azure/active-directory/managed-identities-azure-resources/overview) that has enough permissions ([Reader and AcrDelete](https://docs.microsoft.com/en-us/azure/container-registry/container-registry-roles) at least) to access the ACR and delete images.

## Requirements

The bot requires Python v3.7 and the `pandas` package listed in [`requirements.txt`](./requirements.txt), which can be installed using `pip`:

```bash
pip install -r requirements.txt
```

The bot will need access to the [Microsoft Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest) and the [Docker CLI](https://docs-stage.docker.com/v17.12/install/) in order to query the ACR.

### Installing Azure CLI (on Linux)

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

See the [Microsoft Azure CLI Installation docs](https://docs.microsoft.com/en-gb/cli/azure/install-azure-cli?view=azure-cli-latest) for more installation options.

### Installing Docker CLI (on Linux)

```bash
sudo apt install docker.io -y
sudo usermod -a -G docker $USER
```

## Usage

Run the bot with the following command:

```bash
python DockerCleanUpBot.py \
    --name [-n] ACR_NAME \
    --max-age [-a] AGE \
    --limit [-l] SIZE_LIMIT \
    --identity \
    --dry-run
```

where:

- `ACR_NAME` (string) is the name of the ACR to be cleaned;
- `AGE` (integer, default = 90) is the maximum age in days for images in the ACR;
- `SIZE_LIMIT` (float, default = 2.0) is the maximum size in TB that the ACR is permitted to grow to;
- `--identity` is a Boolean flag allowing the resource to login to Azure with a Managed System Identity; and
- `--dry-run` is a Boolean flag that prevents the images from actually being deleted.

The script will generate a log file (`DockerCleanUpBot.log`) with the output of the actions.

## CRON expression

To run this script at midnight on the first day of every month, use the following cron expression:

```bash
0 0 1 * * cd /path/to/DockerCleanUp && ~/path/to/python DockerCleanUpBot.py [--flags]
```

## Pre-commit Hook

For developing the bot, a pre-commit hook can be installed which will apply [black](https://github.com/psf/black) and [flake8](http://flake8.pycqa.org/en/latest/) to the Python files.
To install the hook, run the following:

```bash
pip install -r requirements-dev.txt
pre-commit install
```
