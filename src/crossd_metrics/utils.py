# -*- coding=utf-8 -*-
import builtins
import re
import time
import typing
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, NewType
import github.PaginatedList  # type: ignore
import github.Repository  # type: ignore
import rich.console
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.request import urlopen, Request
from dateutil.relativedelta import relativedelta

"""Various utility functions and classes for handling GitHub data."""

# regex for matching URLs
regex: str = (
    r"(?:(?:https?|ftp|file):\/\/|www\.|ftp\.)(?:\([-A-Z0-9+&@#\/%=~_|$?!:,.]*\)|[-A-Z0-9+&@#\/%=~_|$?!:,.])*(?:\([-A-Z0-9+&@#\/%=~_|$?!:,.]*\)|[A-Z0-9+&@#\/%=~_|$])"
)
# compiled regex pattern for matching URLs
pattern: re.Pattern = re.compile(regex, re.IGNORECASE | re.MULTILINE)


def get_readme_index(name: str) -> str:
    """Prepares a name for use as an index in a dictionary.
    This function replaces dots and slashes in the name with underscores.

    Args:
      name: str: The name to be prepared for use as an index.

    Returns:
        str: The prepared name with dots and slashes replaced by underscores.

    """
    return name.replace(".", "_").replace("/", "_")


def get_urls(content: str) -> list[str]:
    """Extract URLs from a given string using a regex pattern.

    Args:
      content: str: The string content from which to extract URLs.

    Returns:
        list[str]: A list of URLs extracted from the content.

    """
    return pattern.findall(content)


def merge_dicts(orig: dict | None, *args: dict | None) -> dict:
    """Merges multiple dictionaries into one recursively. Adds values of lists and new values of dicts or overwrites
    existing values.

    Args:
      orig: dict | None: The original dictionary to merge into.
      *args: dict | None: Additional dictionaries to merge into the original.

    Returns:
        dict: The merged dictionary containing all values from the original and additional dictionaries.
    """
    # stores the result
    merged: dict = {}
    # start with the original dictionary or an empty dictionary
    merged.update(orig or {})
    # iterate over all dictionaries to be merged
    for new in args:
        new = new or {}  # not working for mypy inside for statement
        for key in new.keys():
            # if the new dictionary is None, skip it
            # if the key is not in the result dictionary, add it
            if key not in merged:
                merged[key] = new[key]
            else:
                # if the key is in both dictionaries, check the types mismatch
                if type(merged[key]) in [dict, list] and type(merged[key]) != type(new[key]):
                    # if old is dict or list and new is not (e.g. None or other), just overwrite value
                    merged[key] = new[key]
                else:
                    match type(merged[key]):
                        case builtins.dict:
                            # if both are dicts, merge them recursively
                            merged[key] = merge_dicts(merged[key], new[key])
                        case builtins.list:
                            # if both are lists, extend the list with the new values
                            merged[key] = merged[key] + new[key]
                        case _:
                            # if both are not dicts or lists, just overwrite the value
                            merged[key] = new[key]
    return merged


def handle_rate_limit(
    timestamp: str | int, func: Callable, console: typing.Optional[rich.console.Console] = None
) -> typing.Any:
    """Helper function for checking rate limit and sleeping for the specified time.

    Args:
      timestamp: str | int: Sleep until the given timestamp.
      func: Callable: The function to be executed after sleeping.
      console: rich.console.Console: Object for rich log messages (Default value = None)

    Returns:
        typing.Any: The result of the function after sleeping.
    """
    # if no timestamp is given, sleep for 60 seconds
    sleep_time = 60
    # if a timestamp is given, sleep until the given timestamp
    if timestamp:
        sleep_time = int(timestamp) - int(time.time())
    # add a little grace period
    sleep_time += 5
    if console:
        console.log("rate limit exceeded - sleeping for " + str(sleep_time) + " seconds")
    else:
        print("rate limit exceeded - sleeping for " + str(sleep_time) + " seconds")
    time.sleep(sleep_time)
    # if rate limit is still exceed for whatever reason, crash and let the task queue retry later
    # execute the supplied function and return the result
    return func()


def simple_pagination(
    selector: str | list,
    method: Callable,
    filters: list[Callable[[dict], bool]] = [],
) -> Callable:
    """
    Helper function for checking pagination and returning a method preparing the query for the actual pagination.
    If the selector is a string, it will be used to check for pagination. If the selector is a list, it will be used to check for pagination in the data dictionary.

    Args:
      selector: str | list: The selector to be used on the data to check if pagination is necessary.
      method: Callable: The method to be called for the next page.
      filters: list[Callable[[dict],bool]]: Additional checks whether pagination is necessary. (Default value = [])

    Returns:
        Callable : A single method to be called to check for the next page.
    """

    def pagination(data: dict) -> list[Callable] | Callable | None:
        """Return a method preparing the query for the actual pagination.

        Args:
          data: dict: The data dictionary containing the information about the current page.

        Returns:
            list[Callable] | Callable | None: A list of methods or a single method to be called for the next page or None if no pagination is needed.
        """
        selection: dict = {}
        print(selector)
        # if the selector is a string, use it to check for pagination
        if type(selector) == str:
            selection = data["repository"][selector]
        elif type(selector) == list:
            # if the selector is a list, use it to check for pagination in the data dictionary
            # iterate over the list and get the selection
            selection = data
            for elem in selector:
                selection = selection[elem]
        if not selection["pageInfo"]["hasNextPage"]:
            print("no next page")
            return None
        if not all(_filter(data) for _filter in filters):
            # if the filters are not met, return None
            print("filters not fulfilled")
            return None

        # if selection["pageInfo"]["hasNextPage"]:
        # if there is a next page, return the method with the end cursor as argument
        print("method:", method, type(method))
        return [
            lambda: method(
                after=selection["pageInfo"]["endCursor"],
            )
        ]

    return pagination


@dataclass
class Order:
    """Ordering type for sorting data."""

    direction: typing.Literal["ASC", "DESC"]


@dataclass
class IssueOrder(Order):
    """Ordering type for sorting issues."""

    field: typing.Literal["COMMENTS", "CREATED_AT", "UPDATED_AT"]


@dataclass
class PullRequestOrder(Order):
    """Ordering type for sorting pull requests."""

    field: typing.Literal["CREATED_AT", "UPDATED_AT"]


@dataclass
class IssueCommentOrder(Order):
    """Ordering type for sorting issue comments."""

    field: typing.Literal["UPDATED_AT"]


@dataclass
class ReleaseOrder(Order):
    """Ordering type for sorting releases."""

    field: typing.Literal["CREATED_AT", "NAME"]


@dataclass
class RepositoryOrder(Order):
    """Ordering type for sorting repositories."""

    field: typing.Literal["NAME", "CREATED_AT", "UPDATED_AT", "PUSHED_AT", "STARGAZERS"]


# @dataclass
# class RefOrder(Order):
#     """Ordering type for sorting refs."""

#     field: typing.Literal["ALPHABETICAL", "TAG_COMMIT_DATE"]


@dataclass
class AdvisoryOrder(Order):
    """Ordering type for sorting refs."""

    field: typing.Literal["CREATED", "UPDATED", "PUBLISHED"]


IsoDate = NewType("IsoDate", str)  # date in ISO8601 format


def to_prop_camel(orig: str) -> str:
    parts = orig.lower().split("_", 1)
    return parts[0] + parts[-1][0].upper() + parts[1][1:]


def get_security_advisories(
    repo: github.Repository.Repository,
    sort: AdvisoryOrder = AdvisoryOrder("DESC", "PUBLISHED"),
) -> github.PaginatedList.PaginatedList:
    """
    Get the security advisories for a given repository in specified sort order.

    Args:
      repo: github.Repository.Repository: PyGithub Repository object
      sort: Literal["created", "updated", "published"]: attribute to sort after (Default value = "published")

    Returns:
        github.PaginatedList.PaginatedList: A paginated list of security advisories for the repository.
    """
    # github.Repository.Repository.get_security_advisories does not support sorting
    return github.PaginatedList.PaginatedList(
        github.RepositoryAdvisory.RepositoryAdvisory,
        repo._requester,
        f"{repo.url}/security-advisories",
        {"sort": sort.field.lower(), "direction": sort.direction.lower()},
    )


def get_past(since: datetime.datetime | relativedelta | None) -> datetime.datetime | None:
    """
    Get the past date based on the given datetime or timedelta.

    Args:
      since: datetime.datetime | datetime.timedelta | None: The date or time duration to calculate the past date from.

    Returns:
      datetime.datetime | None: If a datetime is provided, it will be returned as is. If a timedelta is provided, the current date minus the timedelta will be returned. If None is provided, None will be returned.
    Raises:
        TypeError: If the input is not of type datetime.datetime, datetime.timedelta or None.
    """
    if type(since) == datetime.datetime:
        return since
    elif type(since) == relativedelta:
        return datetime.datetime.now(datetime.UTC) - since
    elif type(since) == type(None):
        return None
    else:
        raise TypeError("since not of type datetime.datetime, datetime.timedelta or None")


def get_osi_json():
    """
    Use licenseId to check for matching entries
    with retrieved data from GitHub to check,
    if license is OSI approved (isOsiApproved)
    URL = https://raw.githubusercontent.com/spdx/license-list-data/master/json/licenses.json
    """
    url = "https://raw.githubusercontent.com/" + "spdx/license-list-data/master/json/licenses.json"
    response = requests.get(url, timeout=100)
    results_dict = response.json().get("licenses")
    return results_dict


def get_nvds(cve_id: str):
    """
    :param cve_id: CVE id, used to find the cve in the nvd database.
                   e.g. CVE-2022-35920
    :return: base score from NVD or None, if nothing was found
    """
    url = "https://nvd.nist.gov/vuln/detail/" + cve_id
    score = None
    try:
        # response = requests.get(url)
        response = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}))
        soup = BeautifulSoup(response.read(), "html.parser")
        severity_box = soup.find("div", {"id": "Vuln3CvssPanel"})
        # print(severity_box)
        for row in severity_box.find_all("div", {"class": "row no-gutters"}):
            if row.find("span", {"class": "wrapData"}).text == "NVD":
                base_score = severity_box.find("span", {"class": "severityDetail"}).text
                try:
                    score = float(base_score.split()[0])
                except ValueError:
                    pass
    except AttributeError:
        score = None
    return score


def date_filter(
    data: list[dict],
    selector: Callable[[dict], str],
    since: datetime.datetime | relativedelta,
) -> list[dict]:
    """
    Filter a list of dictionaries based on a date.

    Args:
        data: list[dict]: The list of dictionaries to be filtered.
        selector: Callable: A function that takes a dictionary and returns a date ISO8601 string.
        since: datetime.datetime | datetime.timedelta: The date or time duration to filter the data. (Default value = datetime.timedelta(days=30 * 6))
    Returns:
        list[dict]: A list of dictionaries that match the date filter.
    """
    if type(since) == datetime.datetime:
        # if since is a datetime object, use it as is
        past = since
    elif type(since) == relativedelta:
        # if since is a timedelta object, use it to calculate the past date
        past = datetime.datetime.now(datetime.UTC) - since
    else:
        raise TypeError("since not of type datetime.datetime, dateutil.relativedelta.relativedelta")

    res = []
    for elem in data:
        if datetime.datetime.fromisoformat(selector(elem)) > past:
            res.append(elem)
    return res


def get_contributors(data, check_contrib=False) -> int:
    """
    Gets number of contributors.
    :param contributors_data: Data with user and their contributions
    :param check_contrib: True if for contributions has to be checked
    :return: Number of contributors per repository
    """
    # repo_contributors = {}
    # for repo, data in data:
    # contributors_nr = 0
    if check_contrib:
        data = [x for x in data if x["contributions"]]
        # for user in data:
        #     if user and isinstance(user, dict):
        #         contributions = user.get("contributions")
        #         if contributions:
        #             contributors_nr += 1
        # else:
        # contributors_nr = len(data)
        # repo_contributors[repo] = contributors_nr
    return len(data)


CRITICALITY_WEIGHTS = {
    "created_since": {"weight": 1, "max_threshold": 120},
    "updated_since": {"weight": -1, "max_threshold": 120},
    "contributor_count": {"weight": 2, "max_threshold": 5000},
    "org_count": {"weight": 1, "max_threshold": 10},
    "commit_frequency": {"weight": 1, "max_threshold": 1000},
    "recent_releases_count": {"weight": 0.5, "max_threshold": 26},
    "closed_issues_count": {"weight": 0.5, "max_threshold": 5000},
    "updated_issues_count": {"weight": 0.5, "max_threshold": 5000},
    "comment_frequency": {"weight": 1, "max_threshold": 15},
    "dependents_count": {"weight": 2, "max_threshold": 500000},
}


def get_contributor_per_files(commits: list) -> dict[str, set]:
    """
    Getting unique contributors per file and
    retrieving co authors from the commit message.
    :param commit: Single Commit object returned by API
    :return: Files with corresponding contributors
    """
    file_committer = {}
    # for features in commit.values():
    #     for row in features:
    for commit in commits:
        files = commit.get("files")
        try:
            co_authors = set()
            committer_email = commit.get("committer").get("email")
            author_email = commit.get("author").get("email")
            # message = commit.get("message")
            # co_author_line = re.findall(r"Co-authored-by:(.*?)>", message)
            verification = commit.get("has_signature")
            # for value in co_author_line:
            #     co_author = value.split("<")[-1]
            #     co_authors.add(co_author)
            for elem in commit.get("co_authors"):
                co_author = elem.get("email")
                co_authors.add(co_author)
            if committer_email != author_email:
                contributor = author_email
            else:
                if verification:
                    contributor = author_email
                else:
                    contributor = committer_email
        except AttributeError as att_err:
            print(f"Attribute error at commit: {commit}: {att_err}")
            raise
        if co_authors:
            contributors = {contributor} | co_authors
        else:
            contributors = {contributor}
        for file in files:
            filename = file
            # filename = file.get("filename")
            if filename not in file_committer:
                file_committer[filename] = contributors
            else:
                existing_file = file_committer.get(filename)
                if existing_file:
                    file_committer[filename] = existing_file.union(contributors)
    return file_committer


def invert_dict(dictionary: dict) -> dict:
    """
    Change dictionary values to keys.
    """
    inverse = dict()
    for key in dictionary:
        for item in dictionary[key]:
            if item not in inverse:
                inverse[item] = [key]
            else:
                inverse[item].append(key)
    return inverse


def is_branch_active(branch: dict) -> bool:
    # return datetime.datetime.now(datetime.UTC) - datetime.datetime.fromisoformat(
    #     branch["branch"]["commit"]["committedDate"]
    # ) > datetime.timedelta(days=30 * 3)
    return datetime.datetime.fromisoformat(branch["branch"]["commit"]["committedDate"]) > (
        datetime.datetime.now(datetime.UTC) - relativedelta(months=3)
    )


def get_active_branches(branches: list[dict]) -> list[dict]:
    # elem[0]
    return {
        branch["branch"]["name"]: (
            next(filter(None, elem))
            if (elem := branch["branch"]["associatedPullRequests"]["nodes"])
            else {}
        ).get("state", "")
        for branch in branches
        if is_branch_active(branch)
    }


def get_stale_branches(branches: list[dict]) -> list[dict]:
    # elem[0]
    return {
        branch["branch"]["name"]: (
            next(filter(None, elem))
            if (elem := branch["branch"]["associatedPullRequests"]["nodes"])
            else {}
        ).get("state", "")
        for branch in branches
        if not is_branch_active(branch)
    }
