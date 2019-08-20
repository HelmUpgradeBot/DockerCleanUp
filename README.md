# DockerCleanUp

This is an automatable bot to clean up Docker images stored in an Azure Container Registry (ACR) that are 90 days old or more.

- [Overview](#overview)
- [Assumptions DockerCleanUp Makes](#assumptions-dockercleanupbot-makes)
- [Usage](#usage)
- [Requirements](#requirements)

---

## Overview

* Login into the requested ACR via the Azure CLI
* Check the size of the ACR
  * If the ACR size is above a limit, perfom an "aggressive" clean up. This is where the 25 (default setting) largest images in the ACR are deleted in order to reduce running costs.
* Fetch the repositories in the ACR
* Check the manifests for each repository and log the digests of those that are 90 days old or more
* If it's not a dry-run, delete all the logged digests

## Assumptions DockerCleanUpBot Makes

To login to Azure, the bot assumes it's being run from a resource (for example, a Virtual Machine)with a [Managed System Identity](https://docs.microsoft.com/en-gb/azure/active-directory/managed-identities-azure-resources/overview) that has enough permissions ([Reader and AcrDelete](https://docs.microsoft.com/en-us/azure/container-registry/container-registry-roles) at least) to access the ACR and delete images.

## Usage

Run the bot with the following command:

```
python DockerCleanUpBot.py \
    --name [-n] ACR_NAME \
    --max-age [-a] AGE \
    --limit [-l] SIZE_LIMIT \
    --identity \
    --dry-run
```
where:
* `ACR_NAME` (string) is the name of the ACR to be cleaned;
* `AGE` (integer, default = 90) is the maximum age in days for images in the ACR;
* `SIZE_LIMIT` (float, default = 2.0) is the maximum size in TB that the ACR is permitted to grow to;
* `--identity` is a Boolean flag allowing the resource to login to Azure with a Managed System Identity; and
* `--dry-run` is a Boolean flag that prevents the images from actually being deleted.

## Requirements

The bot requires Python v3.7 and the `pandas` package listed in [`requirements.txt`](./requirements.txt), which can be installed using `pip`:

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
