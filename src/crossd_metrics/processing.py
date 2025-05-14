# -*- coding=utf-8 -*-

from crossd_metrics.MultiUser import MultiUser

"""Convencience quality of life functions."""


def get_user_organizations(data: dict) -> dict:
    """Takes the users of a repository and returns their organizations.
    Excludes dependabot[bot] from the list of users.

    Args:
      data: dict: Repository data containing user information.

    Returns:
        dict: A dictionary containing the organizations of the users.
    """
    return (
        MultiUser(
            login=[
                user["login"]
                for user in data["contributors"]["users"]
                if user["login"] != "dependabot[bot]"
            ]
        )
        .ask_organizations()
        .execute(rate_limit=True)
    )
