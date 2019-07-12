# DockerCleanUp

This is an automatable bot to clean up Docker images stored in an Azure Container Registry (ACR) that are 90 days old or more.

## Overview

* Login into the requested ACR via the Azure CLI
* Fetch the repositories in the ACR
* Check the manifests for each repository and log the digests of those that are 90 days old or older
* If it's not a dry-run, delete all the logged digests

## Usage

To run the bot, parse the name of the ACR you'd like to clean as an environment variable:

```
NAME="<acr-name>" python DockerCleanUpBot.py
```

To perform a dry-run, parse the `--dry-run` flag:

```
NAME="<acr-name>" python DockerCleanUpBot.py --dry-run
```

## Requirements

The bot requires Python v3.7 and the `pandas` package listed in [`requirements.txt`](./requirements.txt), which can be installed upsing `pip`:

```
pip install -r requirements.txt
```

The bot will need access to the [Microsoft Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest) in order to query the ACR.
