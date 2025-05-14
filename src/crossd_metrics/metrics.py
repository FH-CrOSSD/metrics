# -*- coding=utf-8 -*-

import datetime
import statistics

from crossd_metrics import constants, utils

"""This module contains functions for calculating various metrics related to GitHub repositories."""


def get_metrics(data: dict) -> dict:
    """Convenience function to retrieve all metrics.

    Args:
      data: dict: repo data retrieved by Repository().ask_all().execute()

    Returns:
        dict: dictionary containing all metrics
    """
    return {
        "mean_pull_requests": mean_pull_requests(data),
        "median_pull_requests": median_pull_requests(data),
        "dependents_count": dependents_count(data),
        "has_security_policy": has_security_policy(data),
        "dependencyCount": dependency_count(data),
        "has_contributing_policy": has_contributing_policy(data),
        "feature_request_count": feature_request_count(data),
        "closed_feature_request_count": closed_feature_request_count(data),
        "has_collaboration_platform": has_collaboration_platform(data),
        "uses_workflows": uses_workflows(data),
        "current_state_workflows": current_state_workflows(data),
        "is_fundable": has_funding_links(data),
        "identity": {
            "name": name(data),
            "owner": owner(data),
            "name_with_owner": name_with_owner(data),
        },
    }


def mean_pull_requests(data: dict) -> float | None:
    """Calculate the mean time between opening and merging pull requests.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        float: mean time in milliseconds or None if no pull requests exist
    """
    # calculate time between opening a pull request and merging it
    diffs = _diff_pull_requests(data)
    if not diffs:
        # no pull requests exist
        return None
    # mean of all pull request merging times and conversion to milliseconds
    return datetime.timedelta(
        seconds=statistics.mean(elem.total_seconds() for elem in diffs)
    ) / datetime.timedelta(milliseconds=1)


def median_pull_requests(data: dict) -> float | None:
    """Calculate the median time between opening and merging pull requests.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        float: median time in milliseconds or None if no pull requests exist
    """
    # calculate time between opening a pull request and merging it
    diffs = _diff_pull_requests(data)
    if not diffs:
        # no pull requests exist
        return None
    # median of all pull request merging times and conversion to milliseconds
    return statistics.median(diffs) / datetime.timedelta(milliseconds=1)  # type: ignore[type-var]


def _diff_pull_requests(data: dict) -> list[datetime.timedelta]:
    """Calculate the times between opening and merging pull requests.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        list[datetime.timedelta]: list of time differences between opening and merging pull requests
    """
    diffs = []
    # calculate time between opening a pull request and merging it
    for elem in data["repository"]["pullRequests"]["edges"]:
        diffs.append(
            datetime.datetime.strptime(elem["node"]["mergedAt"], "%Y-%m-%dT%H:%M:%S%z")
            - datetime.datetime.strptime(elem["node"]["createdAt"], "%Y-%m-%dT%H:%M:%S%z")
        )
    return diffs


def name(data: dict) -> str:
    """Get the name of the repository.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        str: name of the repository
    """
    return data["repository"]["name"]


def name_with_owner(data: dict) -> str:
    """Get the name of the repository with owner.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        str: name of the repository with owner
    """
    return data["repository"]["nameWithOwner"]


def owner(data: dict) -> str:
    """Get the owner of the repository.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        str: owner of the repository
    """
    return data["repository"]["owner"]["login"]


def dependents_count(data: dict) -> int:
    """Get the number of dependents of the repository.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        int: number of dependents of the repository
    """
    return data["dependents"]


def has_security_policy(data: dict) -> bool:
    """Check if the repository has a security policy.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        bool: True if the repository has a security policy, False otherwise
    """
    return data["repository"]["isSecurityPolicyEnabled"]


def dependency_count(data: dict) -> int:
    """Get the number of dependencies of the repository.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        int: number of dependencies of the repository
    """
    # dependency count of all dependency files github knows
    return sum(
        elem["node"]["dependenciesCount"]
        for elem in data["repository"]["dependencyGraphManifests"]["edges"]
    )


def has_contributing_policy(data: dict) -> bool:
    """Check if the repository has a contributing policy.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        bool: True if the repository has a contributing policy, False otherwise
    """
    return bool(
        data["repository"]["contributing_md"]
        or data["repository"]["contributing_txt"]
        or data["repository"]["contributing_raw"]
    )


def feature_request_count(data: dict) -> int:
    """Get the number of feature requests of the repository.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        int: number of feature requests of the repository
    """
    return data["repository"]["feature_requests"]["totalCount"]


def closed_feature_request_count(data: dict) -> int:
    """Get the number of closed feature requests of the repository.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        int: number of closed feature requests of the repository
    """
    return data["repository"]["closed_feature_requests"]["totalCount"]


def has_collaboration_platform(data: dict) -> bool:
    """Check if the repository features a collaboration platform.
    This function checks if the repository has a Discord, Reddit, or Slack URL in its README files.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        bool: True if the repository has a collaboration platform, False otherwise
    """
    # check if readme has social platform urls
    res: dict = {"discord": [], "reddit": [], "slack": []}
    # get all readme contents
    contents = [data["repository"][utils.get_readme_index(elem)] for elem in constants.readmes]
    urls = []
    # get all urls from readme contents
    for elem in contents:
        if elem:
            urls.extend(utils.get_urls(elem["text"]))

    for url in urls:
        url = url.strip()
        if "discord.com" in url or "discord.gg" in url or url.endswith("/discord"):
            res["discord"].append(url)
        if "reddit.com/r/" in url:
            res["reddit"].append(url)
        if ".slack.com" in url:
            res["slack"].append(url)

    return any(res.values())


def uses_workflows(data: dict) -> bool:
    """Check if the repository uses workflows.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        bool: True if the repository uses workflows, False otherwise
    """
    return any([wf["state"] == "active" for wf in data["workflows"]])


def current_state_workflows(data: dict) -> dict:
    """Get the current state of workflows.
    This function returns the last run of each workflow in the repository.

    Args:
      data: dict: repo data retrieved by Repository methods.

    Returns:
        dict: dictionary containing the last run of each workflow
    """
    res: dict = {}

    for elem in data["workflows"]:
        # get last run of each workflow
        res.setdefault(
            elem["name"],
            {
                "created_at": elem["last_run"]["created_at"],
                "conclusion": elem["last_run"]["conclusion"],
            },
        )
        # check if run is newer than current
        if elem["last_run"]["created_at"] > res[elem["name"]]["created_at"]:
            res[elem["name"]] = {
                "created_at": elem["last_run"]["created_at"],
                "conclusion": elem["last_run"]["conclusion"],
            }
    return res


def has_funding_links(data: dict) -> bool:
    """Check if the repository has funding links.

    Args:
      data: dir: repo data retrieved by Repository methods.

    Returns:
        bool: True if the repository has funding links, False otherwise
    """
    return bool(data["repository"]["fundingLinks"])
