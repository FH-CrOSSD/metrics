# CrOSSD metrics

This library provides functionality to retrieve data about a GitHub repository and calculate various metrics based on that data.
It uses mainly the GitHub GraphQL API.

This repository is part of the [CrOSSD](https://health.crossd.tech/about) project and powers the `c-drone` and `m-drone` (`worker-drone`) components.  
**See our main repository [here](https://github.com/FH-CrOSSD/crossd).**

## Installation

For installing PDM see [their website](https://pdm-project.org/en/stable/).
Afterwards you can install the dependencies with `pdm install`.

You can also use this repository as dependency for your own project.
For use with a PDM project see [local dependencies](https://pdm-project.org/latest/usage/dependency/#editable-dependencies)
or for use in a Docker image see [this](https://pdm-project.org/latest/usage/advanced/).

## Usage

Short basic example:

```python
from crossd_metrics.metrics import get_metrics
from crossd_metrics.Repository import Repository
# retrieve GitHub data
res = Repository(owner="FH-CrOSSD", name="crossd.tech").ask_all().execute(rate_limit=True, verbose=True)
print(res)
# calculate metrics and print them
print(get_metrics(res))
```

## Secrets

For accessing the GitHub API, a API token needs to be provided.
The code reads the `GH_TOKEN` environment variable, which can also be provided via `.env` file.

## Acknowledgements

The financial support from Internetstiftung/Netidee is gratefully acknowledged. The mission of Netidee is to support development of open-source tools for more accessible and versatile use of the Internet in Austria.
