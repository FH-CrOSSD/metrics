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
        console.log("rate limit exceeded - sleeping for " + str(sleep_time))
    else:
        print("rate limit exceeded - sleeping for " + str(sleep_time))
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
            return None
        if not all(_filter(data) for _filter in filters):
            # if the filters are not met, return None
            return None

        # if selection["pageInfo"]["hasNextPage"]:
        # if there is a next page, return the method with the end cursor as argument
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
class RepositoryOrder(Order):
    """Ordering type for sorting repositories."""

    field: typing.Literal["NAME", "CREATED_AT", "UPDATED_AT", "PUSHED_AT", "STARGAZERS"]


@dataclass
class RefOrder(Order):
    """Ordering type for sorting refs."""

    field: typing.Literal["ALPHABETICAL", "TAG_COMMIT_DATE"]


IsoDate = NewType("IsoDate", str)  # date in ISO8601 format


def get_security_advisories(
    repo: github.Repository.Repository,
    sort: Literal["created", "updated", "published"] = "published",
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
        {"sort": sort},
    )


def get_past(since: datetime.datetime | datetime.timedelta | None) -> datetime.datetime | None:
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
    elif type(since) == datetime.timedelta:
        return datetime.datetime.now(datetime.UTC) - since
    elif type(since) == type(None):
        return None
    else:
        raise TypeError("since not of type datetime.datetime, datetime.timedelta or None")
