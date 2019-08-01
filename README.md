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

The bot will need access to the [Microsoft Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest) in order to query the ACR.
