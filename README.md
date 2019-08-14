# DockerCleanUp

This is an automatable bot to clean up Docker images stored in an Azure Container Registry (ACR) that are 90 days old or more.

- [Overview](#overview)
- [Assumptions DockerCleanUp Makes](#assumptions-dockercleanupbot-makes)
- [Usage](#usage)
- [Requirements](#requirements)

---

## Overview

* Login into the requested ACR via the Azure CLI
* Fetch the repositories in the ACR
* Check the manifests for each repository and log the digests of those that are 90 days old or older
* If it's not a dry-run, delete all the logged digests

## Assumptions DockerCleanUpBot Makes

To login to Azure, the bot assumes it's being running from a resource with a [Managed System Identity](https://docs.microsoft.com/en-gb/azure/active-directory/managed-identities-azure-resources/overview) with enough permissions ([Reader and AcrDelete](https://docs.microsoft.com/en-us/azure/container-registry/container-registry-roles) at least) to access the ACR.

## Usage

Run the bot with the following command:

```
python DockerCleanUpBot.py --name ACR-NAME
```

To perform a dry-run, parse the `--dry-run` flag:

```
python DockerCleanUpBot.py --name ACR-NAME --dry-run
```

## Requirements

The bot requires Python v3.7 and the `pandas` package listed in [`requirements.txt`](./requirements.txt), which can be installed upsing `pip`:

```
pip install -r requirements.txt
```

The bot will need access to the [Microsoft Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest) and the [Docker CLI](https://docs-stage.docker.com/v17.12/install/) in order to query the ACR.

### Installing Azure CLI

```
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### Installing Docker CLI (on Linux)

```
sudo apt install docker.io -y
sudo usermod -a -G docker $USER
```

## CRON expression

Run this script at midnight on the first day of every month:

```
0 0 1 * * cd /path/to/DockerCleanUp && ~/path/to/python DockerCleanUpBot.py [--flags]
```
