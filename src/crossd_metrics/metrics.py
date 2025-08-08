# -*- coding=utf-8 -*-

import collections
import datetime
import math
import os
import re
import statistics
from pathlib import Path
from typing import Union

from crossd_metrics import constants, utils
from dateutil.relativedelta import relativedelta

"""This module contains functions for calculating various metrics related to GitHub repositories."""


def get_metrics(data: dict) -> dict:
    """Convenience function to retrieve all metrics.

    Args:
      data (dict): repo data retrieved by Repository().ask_all().execute()

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
        "maturity_level": maturity_level(data),
        "osi_approved_license": osi_approved_license(data),
        "technical_fork": technical_fork(data),
        "criticality_score": criticality_score(data),
        "pull_requests": pull_requests(data),
        "project_velocity": project_velocity(data),
        "github_community_health_percentage": github_community_health_percentage(data),
        "issues": issues(data),
        "support_rate": support_rate(data),
        "code_dependency": code_dependency(data),
        "security_advisories": security_advisories(data),
        "contributions_distributions": contributions_distributions(data),
        "number_of_support_contributors": number_of_support_contributors(data),
        "size_of_community": size_of_community(data),
        "churn": churn(data),
        "branch_lifecycle": branch_lifecycle(data),
        "elephant_factor": elephant_factor(data),
        "identity": {
            "name": name(data),
            "owner": owner(data),
            "name_with_owner": name_with_owner(data),
        },
    }


def mean_pull_requests(data: dict) -> float | None:
    """Calculate the mean time between opening and merging pull requests.

    Args:
      data (dict): repo data retrieved by Repository methods.

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
      data (dict): repo data retrieved by Repository methods.

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
      data (dict): repo data retrieved by Repository methods.

    Returns:
        list[datetime.timedelta]: list of time differences between opening and merging pull requests
    """
    diffs = []
    # calculate time between opening a pull request and merging it
    for elem in data["repository"]["pullRequests"]["edges"]:
        if elem["node"]["mergedAt"] and elem["node"]["createdAt"]:
            diffs.append(
                datetime.datetime.strptime(elem["node"]["mergedAt"], "%Y-%m-%dT%H:%M:%S%z")
                - datetime.datetime.strptime(elem["node"]["createdAt"], "%Y-%m-%dT%H:%M:%S%z")
            )
    return diffs


def name(data: dict) -> str:
    """Get the name of the repository.

    Args:
      data (dict): repo data retrieved by Repository methods.

    Returns:
        str: name of the repository
    """
    return data["repository"]["name"]


def name_with_owner(data: dict) -> str:
    """Get the name of the repository with owner.

    Args:
      data (dict): repo data retrieved by Repository methods.

    Returns:
        str: name of the repository with owner
    """
    return data["repository"]["nameWithOwner"]


def owner(data: dict) -> str:
    """Get the owner of the repository.

    Args:
      data (dict): repo data retrieved by Repository methods.

    Returns:
        str: owner of the repository
    """
    return data["repository"]["owner"]["login"]


def dependents_count(data: dict) -> int:
    """Get the number of dependents of the repository.

    Args:
      data (dict): repo data retrieved by Repository methods.

    Returns:
        int: number of dependents of the repository
    """
    return data["dependents"]["count"]


def has_security_policy(data: dict) -> bool:
    """Check if the repository has a security policy.

    Args:
      data (dict): repo data retrieved by Repository methods.

    Returns:
        bool: True if the repository has a security policy, False otherwise
    """
    return data["repository"]["isSecurityPolicyEnabled"]


def dependency_count_graphql(data: dict) -> int:
    """Get the number of dependencies of the repository retrieved per graphql.

    Args:
      data (dict): repo data retrieved by Repository methods.

    Returns:
        int: number of dependencies of the repository
    """
    # dependency count of all dependency files github knows
    return sum(
        elem["node"]["dependenciesCount"]
        for elem in data["repository"]["dependencyGraphManifests"]["edges"]
    )


def dependency_count(data: dict) -> int:
    """Get the number of dependencies of the repository.

    Args:
      data (dict): repo data retrieved by Repository methods.

    Returns:
        int: number of dependencies of the repository
    """
    # dependency count via sbom or crawled from website
    return data["dependencies"]["count"]


def has_contributing_policy(data: dict) -> bool:
    """Check if the repository has a contributing policy.

    Args:
      data (dict): repo data retrieved by Repository methods.

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
      data (dict): repo data retrieved by Repository methods.

    Returns:
        int: number of feature requests of the repository
    """
    return data["repository"]["feature_requests"]["totalCount"]


def closed_feature_request_count(data: dict) -> int:
    """Get the number of closed feature requests of the repository.

    Args:
      data (dict): repo data retrieved by Repository methods.

    Returns:
        int: number of closed feature requests of the repository
    """
    return data["repository"]["closed_feature_requests"]["totalCount"]


def has_collaboration_platform(data: dict) -> bool:
    """Check if the repository features a collaboration platform.
    This function checks if the repository has a Discord, Reddit, or Slack URL in its README files.

    Args:
      data (dict): repo data retrieved by Repository methods.

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
      data (dict): repo data retrieved by Repository methods.

    Returns:
        bool: True if the repository uses workflows, False otherwise
    """
    return any([wf["state"] == "active" for wf in data["workflows"]])


def current_state_workflows(data: dict) -> dict:
    """Get the current state of workflows.
    This function returns the last run of each workflow in the repository.

    Args:
      data (dict): repo data retrieved by Repository methods.

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
      data (dir): repo data retrieved by Repository methods.

    Returns:
        bool: True if the repository has funding links, False otherwise
    """
    return bool(data["repository"]["fundingLinks"])


def osi_approved_license(data: dict) -> str:
    """
    Checks if a repos license is osi approved.

    Args:
      data (dir): repo data retrieved by Repository methods.

    Returns:
        str: either "osi_approved", "not_osi_approved" or "unknown".

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    osi_licenses = utils.get_osi_json()
    license_return = None
    if not data["repository"]["licenseInfo"] or not data["repository"]["licenseInfo"]["spdxId"]:
        license_return = "not_provided"
    else:
        spdx_id = data["repository"]["licenseInfo"]["spdxId"].strip()
        for osi_license in osi_licenses:
            licence_id = osi_license.get("licenseId").strip()
            if spdx_id == licence_id:
                osi_approved = osi_license.get("isOsiApproved")
                if osi_approved is True:
                    license_return = "osi_approved"
                elif osi_approved is False:
                    license_return = "not_osi_approved"
                break
    if not license_return:
        license_return = "not_found"
    return license_return


def churn(data: dict) -> float:
    """
    Calculate churn score for a given list of repositories.

    Args:
      data (dict): Request object containing repository info.

    Returns:
      dict: Churn score for each repository.

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    # limit commits to the last month
    commits = utils.date_filter(
        data["commits"], lambda x: x["committed_iso"], relativedelta(months=1)
    )
    churn_score = None
    if commits:
        lines_added = 0
        lines_deleted = 0
        churn_score = 0
        for commit in commits:
            additions = commit["insertions"]
            deletions = commit["deletions"]
            lines_added += additions
            lines_deleted += deletions
        if lines_added > 0:
            churn_score = (lines_deleted / lines_added) * 100
        else:
            churn_score = None
    return churn_score


def code_dependency(data: dict) -> dict:
    """
    Dependencies retrieved from GitHub's Dependency Graph.
    Upstream dependencies show on how many other projects
    the passed repositories depend on -> GitHub Dependencies.
    Downstream shoe how many other repositories depend on the
    passed repositories -> GitHub Dependents.

    Args:
      data (dict): Request object containing repository info.

    Returns:
      dict: A tuple containing total upstream and downstream dependencies,
             as well as visible downstream dependencies.
    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    dependencies = {}
    dependencies = {
        "total_upstream": data["dependencies"]["count"],
        "total_downstream": data["dependents"]["count"],
    }
    return dependencies


def github_community_health_percentage(data: dict) -> dict[str, float | bool]:
    """
    Retrieves information about the GitHub community health percentage metric.
    As the formula introduced by GitHub is questionable, potential relevant
    information is summarized by indicating,
    if it is available (True) or not (False).
    This is implied by the outdated formula,
    referring to the existence of certain files
    (readme, contributing, license, code of conduct).

    Args:
        data (dict): The data dictionary containing the metric information.
    Returns:
        dict[str, float | bool]: A dictionary containing the
        percentage of the GitHub community health and a boolean indicating
        if it is available.
    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    # data = data["community_profile"]
    # score = data.get("health_percentage")
    # description = bool(data.get("description"))
    # documentation = bool(data.get("documentation"))
    # code_of_conduct = bool(data.get("files").get("code_of_conduct"))
    # contributing = bool(data.get("files").get("contributing"))
    # issue_template = bool(data.get("files").get("issue_template"))
    # pull_request_template = bool(data.get("files").get("pull_request_template"))
    # license_bool = bool(data.get("files").get("license"))
    # readme = bool(data.get("files").get("readme"))

    security_policy = bool(data.get("repository").get("isSecurityPolicyEnabled"))
    license_bool = bool(data.get("repository").get("licenseInfo"))
    contributing = bool(data.get("repository").get("contributingGuidelines"))
    code_of_conduct = bool(data.get("repository").get("codeOfConduct"))
    description = bool(data.get("repository").get("description"))
    documentation = bool(data.get("repository").get("homepageUrl"))
    pull_request_template = bool(data.get("repository").get("pullRequestTemplates"))
    readme = any([data["repository"][utils.get_readme_index(elem)] for elem in constants.readmes])
    issue_template = bool(data.get("repository").get("issueTemplates"))
    if not issue_template:
        if folder := data.get("repository").get("issueTemplateFolder"):
            counter = collections.Counter(
                entry["extension"]
                for entry in folder["entries"]
                if entry["path"] != ".github/ISSUE_TEMPLATE/config.yml"
            )
            issue_template = counter[".yml"] + counter[".md"] > 0

    info_list = [
        description,
        # documentation,
        code_of_conduct,
        contributing,
        issue_template,
        pull_request_template,
        license_bool,
        readme,
        security_policy,
    ]
    print(info_list)
    true_count = info_list.count(True)
    false_count = info_list.count(False)
    if sum(info_list) > 0:
        custom_health_percentage = (sum(info_list) / len(info_list)) * 100
    else:
        custom_health_percentage = None
    infos = {
        # "community_health_score": score,
        "community_health_score": None,
        "custom_health_score": custom_health_percentage,
        "true_count": true_count,
        "false_count": false_count,
        "description": description,
        "documentation": documentation,
        "code_of_conduct": code_of_conduct,
        "contributing": contributing,
        "issue_template": issue_template,
        "pull_request_template": pull_request_template,
        "license": license_bool,
        "readme": readme,
        "security_policy": security_policy,
    }
    return infos


def pull_requests(data: dict) -> dict[str, float]:
    """
    Contains information about:
    - Total number of pulls
    - Average closing time (Difference of creation and close date)
    - Ratio per state (open, closed and merged)

    Args:
      data (dict): A dictionary containing repository information.

    Returns:
      dict[str, float]: A dictionary with parameter names as keys and values
                        representing the corresponding metrics.
    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    data = utils.date_filter(
        data["repository"]["pullRequests"]["edges"],
        lambda x: x["node"]["updatedAt"],
        relativedelta(months=6),
    )
    state_open = 0
    state_closed = 0
    pulls_merged = 0
    avg_date_diff = None
    ratio_open = None
    ratio_closed = None
    ratio_merged = None
    total_pulls = len(data)
    date_diffs = []
    if data:
        for pull in data:
            state = pull["node"].get("state", "")
            closed_at = pull["node"].get("closedAt")
            created_at = pull["node"].get("createdAt")
            merged_at = pull["node"].get("mergedAt")
            created_at = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
            if closed_at:
                closed_at = datetime.datetime.strptime(closed_at, "%Y-%m-%dT%H:%M:%SZ")
            if merged_at:
                merged_at = datetime.datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ")
                pulls_merged += 1
                if closed_at:
                    if closed_at == merged_at:
                        date_diff = closed_at - created_at
                        date_diffs.append(date_diff.days)
            if state.lower() == "open":
                state_open += 1
            elif state.lower() == "closed":
                state_closed += 1
        if len(date_diffs) > 0:
            avg_date_diff = statistics.fmean(date_diffs)

        if total_pulls > 0:
            ratio_open = (state_open / total_pulls) * 100
            ratio_closed = (state_closed / total_pulls) * 100
            ratio_merged = (pulls_merged / total_pulls) * 100
    pull_results = {
        "total_pulls": total_pulls,
        "avg_pull_closing_days": avg_date_diff,
        "ratio_open_total": ratio_open,
        "ratio_closed_total": ratio_closed,
        "ratio_merged_total": ratio_merged,
    }
    return pull_results


def maturity_level(data: dict) -> int:
    """
    Calculate the maturity level of a given repository based on its
    age, number of issues, and releases.

    Args:
        data (dict): A dictionary containing information about the repository.

    Returns:
        int: The maturity level of the repository.

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    age_score = 0
    issue_score = 0
    release_score = 0
    created_at = data["repository"].get("createdAt")
    created_at = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").date()
    dates = relativedelta(datetime.date.today(), created_at)
    years = dates.years
    months = dates.months
    # score = 0
    # Age > 3 years
    if (years == 3 and months > 0) or (years > 3):
        age_score = 5
    # Age > 2-3 years
    elif (years == 2 and months > 0) or (years == 3 and months == 0):
        age_score = 4
    # Age > 1-2 years
    elif (years == 2 and months == 0) or (years == 1 and months > 0):
        age_score = 3
    # Age 2-12 months
    elif (years == 1 and months == 0) or (years == 0 and months >= 2):
        age_score = 2
    # Age < 2 months
    elif years == 0 and months < 2:
        age_score = 1
    age_score = age_score / 5

    issues = utils.date_filter(
        data["repository"]["issues"]["edges"],
        lambda x: x["node"]["updatedAt"],
        relativedelta(months=6),
    )

    pulls = utils.date_filter(
        data["repository"]["pullRequests"]["edges"],
        lambda x: x["node"]["updatedAt"],
        relativedelta(months=6),
    )

    nr_of_issues = len(issues + pulls)
    if nr_of_issues > 1000:
        issue_score = 1
    elif nr_of_issues > 500 and nr_of_issues < 1000:
        issue_score = 2
    elif nr_of_issues > 100 and nr_of_issues <= 500:
        issue_score = 3
    elif nr_of_issues > 50 and nr_of_issues <= 100:
        issue_score = 4
    elif nr_of_issues <= 50:
        issue_score = 5
    issue_score = issue_score / 5

    releases = utils.date_filter(
        data["repository"]["releases"]["edges"],
        lambda x: x["node"]["publishedAt"],
        relativedelta(months=12),
    )

    if len(releases) == 0:
        release_score = 1
    elif len(releases) >= 1 and len(releases) <= 3:
        release_score = 3
    else:
        release_score = 5
    release_score = release_score / 5
    score_sum = age_score + issue_score + release_score
    result = score_sum / 3 * 100
    return result


def technical_fork(data: dict) -> dict[str, int | float]:
    """
    Total number of forks and average creation time.

    Args:
        data (dict): Data from the GitHub API.

    Returns:
        dict: Technical Fork Metrics.

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    fork_results = {}
    data = utils.date_filter(
        data["repository"]["forks"]["nodes"],
        lambda x: x["createdAt"],
        relativedelta(months=6),
    )
    fork_nr = 0
    average_per_week = None
    if data:
        created_at_times = []
        for fork in data:
            fork_created_at = fork.get("createdAt")
            fork_date = datetime.datetime.strptime(fork_created_at, "%Y-%m-%dT%H:%M:%SZ")
            created_at_times.append(fork_date)
            # filter out empty objects (should be rest only)
            fork_id = fork.get("id")
            if fork_id:
                fork_nr += 1

        if created_at_times:
            # Sort the datetime list
            created_at_times.sort()
            earliest_date = created_at_times[0].date()
            latest_date = created_at_times[-1].date()
            num_weeks = (latest_date - earliest_date).days // 7 + 1
            # Count the number of elements per week
            elements_per_week = [0] * num_weeks
            for fork_datetime in created_at_times:
                week_index = (fork_datetime.date() - earliest_date).days // 7
                elements_per_week[week_index] += 1
            average_per_week = round(statistics.fmean(elements_per_week))
    fork_results = {
        "total_forks": fork_nr,
        "average_forks_created_per_week": average_per_week,
    }
    return fork_results


def criticality_score(data: dict) -> float:
    """
    Calculates the criticality score for a given repository.
    The criticality score is based on the number of commits and
    the number of contributors.

    Args:
        data (dict): Data object containing the necessary information to calculate
        the criticality score.

    Returns:
        float: Criticality score for the given repository.

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    # filter_date = datetime.date.today()
    filter_date = datetime.datetime.now(datetime.UTC)
    # scores_per_repo = {}
    # criticality_score_per_repo = {}
    # created_since, updated_since
    # repository_data = base_data.get("repository")
    # commit_data = base_data.get("commits")
    # release_data = base_data.get("release")
    # issues_data = base_data.get("issue")
    # issue_comments = base_data.get("issue_comments")
    # dependents = base_data.get("downstream_dependencies")
    # repo_organizations = base_data.get("organizations")
    # if (
    #     repository_data
    #     and contributor_data
    #     and commit_data
    #     and release_data
    #     and issues_data
    #     and issue_comments
    #     and dependents
    #     and repo_organizations
    # ):
    # log.info("Data available. Starting calculation...")
    # for repo, data in repository_data.items():
    created_at = data["repository"].get("createdAt")
    created_at = datetime.datetime.fromisoformat(created_at)  # , "%Y-%m-%dT%H:%M:%SZ")
    updated_at = data["repository"].get("updatedAt")
    updated_at = datetime.datetime.fromisoformat(updated_at)  # , "%Y-%m-%dT%H:%M:%SZ")
    dates = relativedelta(filter_date, created_at)
    months = dates.months + (dates.years * 12)
    diff_updated_today = relativedelta(filter_date, updated_at)
    diff_updated_today = diff_updated_today.months + (diff_updated_today.years * 12)
    scores = {
        "created_since": months,
        "updated_since": diff_updated_today,
    }
    # contributor_count
    contributor_count = utils.get_contributors(data["contributors"]["users"], check_contrib=True)
    # cont_count = contributor_count.get(repo)
    # if cont_count:
    scores.update({"contributor_count": contributor_count})
    # org_count
    org_count = len(
        set(
            org["login"]
            for user in data["organizations"]
            if "organizations" in data["organizations"][user]
            for org in data["organizations"][user]["organizations"]["nodes"]
        )
    )
    # org_count = repo_organizations.get(repo)
    # if org_count:
    #     org_num = len(org_count)
    # else:
    #     org_num = 0
    scores.update({"org_count": org_count})
    # commit_frequency
    # commits = commit_data.get(repo)
    commits = utils.date_filter(
        data["commits"],
        lambda x: x["authored_iso"],
        #  datetime.timedelta(days=30 * 12)
        relativedelta(months=12),
    )
    average_per_week = 0
    repo_commit_dates = []
    if commits:
        for commit in commits:
            # try:
            # commit_date = commit.get("commit").get("author").get("date")
            commit_date = commit.get("authored_iso")
            commit_date = datetime.datetime.fromisoformat(commit_date)  # , "%Y-%m-%dT%H:%M:%SZ")
            commit_date = commit_date.astimezone(datetime.timezone.utc)
            repo_commit_dates.append(commit_date)
        # except KeyError:
        #     continue
        if len(repo_commit_dates) > 1:
            # Sort the datetime list
            repo_commit_dates.sort()
            earliest_date = repo_commit_dates[0].date()
            latest_date = repo_commit_dates[-1].date()
            num_weeks = (latest_date - earliest_date).days // 7 + 1
            # Count the number of elements per week
            elements_per_week = [0] * num_weeks
            for commit_datetime in repo_commit_dates:
                week_index = (commit_datetime.date() - earliest_date).days // 7
                elements_per_week[week_index] += 1
            average_per_week = statistics.fmean(elements_per_week)
    scores.update({"commit_frequency": average_per_week})
    # recent_releases_count
    # releases = release_data.get(repo)
    # if releases:
    #     num_releases = len(releases)
    # else:
    #     num_releases = 0
    num_releases = len(
        utils.date_filter(
            data["repository"]["releases"]["edges"],
            lambda x: x["node"]["publishedAt"],
            # datetime.timedelta(days=30 * 12),
            relativedelta(months=12),
        )
    )
    scores.update({"recent_releases_count": num_releases})
    # closed_issues_count & updated_issues_count
    issues_list = utils.date_filter(
        data["repository"]["issues"]["edges"],
        lambda x: x["node"]["updatedAt"],
        relativedelta(months=3),
        # datetime.timedelta(days=30 * 3),
    )

    closed_issues = 0
    updated_issues = 0
    if issues_list:
        for issue in issues_list:
            issue = issue["node"]
            closed_at = issue.get("closedAt")
            updated_at = issue.get("updatedAt")
            if closed_at:
                closed_date = datetime.datetime.fromisoformat(closed_at)
                closed_diff = filter_date - closed_date
                if closed_diff.days <= 90:
                    closed_issues += 1
            if updated_at:
                updated_date = datetime.datetime.fromisoformat(updated_at)
                updated_diff = filter_date - updated_date
                if updated_diff.days <= 90:
                    updated_issues += 1
    scores.update(
        {
            "closed_issues_count": closed_issues,
            "updated_issues_count": updated_issues,
        }
    )
    # comment_frequency
    # issues_dict = issue_comments.get(repo)
    issue_keys = [key for key in data["repository"].keys() if re.match(r"^issue\d+$", key)]
    avg_comment_count = 0
    if issue_keys:
        comment_count_list = []
        # for issue, comments in issues_dict.items(
        for issue in issue_keys:
            comment_len = 0
            comments = utils.date_filter(
                data["repository"][issue]["comments"]["edges"],
                lambda x: x["node"]["updatedAt"],
                # datetime.timedelta(days=30 * 3),
                relativedelta(months=3),
            )
            for comment in comments:
                if comment.get("id"):
                    comment_updated_at = comment.get("updatedAt")
                    comment_updated_at = datetime.datetime.fromisoformat(comment_updated_at).date()
                    if comment_updated_at > filter_date:
                        comment_len += 1
            comment_count_list.append(comment_len)
        if comment_count_list:
            avg_comment_count = statistics.fmean(comment_count_list)
    scores.update({"comment_frequency": avg_comment_count})
    # dependents_count
    downstream_dep = data["dependents"]["count"]
    dep_count = 0
    if downstream_dep:
        dep_count = downstream_dep
    scores.update({"dependents_count": dep_count})

    # source_path = Path(__file__).resolve()
    # source_dir = source_path.parent

    weights = utils.CRITICALITY_WEIGHTS
    # open(
    #     os.path.join(source_dir, "criticality_score_weights.json"), encoding="utf-8"
    # )
    # weights_json = open(
    #     r"mdi_thesis\criticality_score_weights.json",
    #     encoding="utf-8")
    # weights = json.load(weights_json)
    weight_sum = 0
    for elements in weights.values():
        weight = elements.get("weight")
        weight_sum += weight
    # for  param in scores.items():
    form_1 = 1 / weight_sum
    sum_alpha = 0
    for param_name, value in scores.items():
        log_1 = math.log(1 + value)
        max_threshold = weights.get(param_name).get("max_threshold")
        log_2 = math.log(1 + max(value, max_threshold))
        if log_2 == 0:
            res_fraction = 1
        else:
            res_fraction = log_1 / log_2
        weight = weights.get(param_name).get("weight")
        res_1 = weight * res_fraction
        sum_alpha += res_1
    res_2 = round((form_1 * sum_alpha), 2) * 100
    # criticality_score = res2

    return res_2


def project_velocity(data: dict) -> dict[str, float]:
    """
    Calculates information about a projects velocity concerning
    issues and their resolving time. Issues also include pulls,
    bc. all pulls are issues, but not all issues are pulls.

    Args:
        data (dict): Data containing project information.

    Returns:
        dict[str, float]: A dictionary containing the project's velocity information, including the
        total number of issues, the average issue resolving time in days,
        the ratio of open and closed issues to total issues and
        information about the number of pulls.

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    velocity_results = {}
    # issues_pulls = base_data.get("issue")
    issues = utils.date_filter(
        data["repository"]["issues"]["edges"],
        lambda x: x["node"]["updatedAt"],
        # datetime.timedelta(days=30 * 6),
        relativedelta(months=6),
    )
    pulls = utils.date_filter(
        data["repository"]["pullRequests"]["edges"],
        lambda x: x["node"]["updatedAt"],
        # datetime.timedelta(days=30 * 6),
        relativedelta(months=6),
    )
    # repository_data = base_data.get("repository")
    # if repository_data and issues_pulls:
    # log.info("Data available. Starting calculation...")
    # for repo in repository_data:
    # data = issues_pulls.get(repo)
    closed_issues = 0
    open_issues = 0
    total_issues = len(issues) + len(pulls)
    date_diffs = []
    # pull_issue_list = []
    ratio_open = None
    ratio_closed = None
    ratio_pull_issue = None
    avg_date_diff = None
    pull_count = None
    no_pull_count = None
    # if data:
    for issue in issues + pulls:
        # pull_request_id = issue.get("pull_request")
        # pull_request_id = issue["node"]["closedByPullRequestsReferences"]["totalCount"]
        # is_pull_request = bool(pull_request_id)
        # pull_issue_list.append(is_pull_request)
        # state = issue.get("state")
        state = issue["node"]["state"]
        created_at = issue["node"]["createdAt"]
        created_at = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
        if state.lower() == "open":
            open_issues += 1
        elif state.lower() in ("closed", "merged"):
            closed_issues += 1
            closed_at = issue["node"]["closedAt"]
            if closed_at:
                closed_at = datetime.datetime.strptime(closed_at, "%Y-%m-%dT%H:%M:%SZ")
            date_diff = closed_at - created_at
            date_diffs.append(date_diff.days)
    # pull_count = pull_issue_list.count(True)
    pull_count = len(pulls)
    no_pull_count = len(issues)
    # no_pull_count = pull_issue_list.count(False)
    if len(date_diffs) > 0:
        avg_date_diff = round(statistics.fmean(date_diffs))
    if total_issues > 0:
        ratio_open = (open_issues / total_issues) * 100
        ratio_closed = (closed_issues / total_issues) * 100
        ratio_pull_issue = (pull_count / total_issues) * 100
    velocity_results = {
        "total_issues": total_issues,
        "closed_issues": closed_issues,
        "open_issues": open_issues,
        "pull_count": pull_count,
        "no_pull_count": no_pull_count,
        "ratio_pull_issue": ratio_pull_issue,
        "avg_issue_resolving_days": avg_date_diff,
        "ratio_open_total": ratio_open,
        "ratio_closed_total": ratio_closed,
    }
    # else:
    #     log.info("No data available. Returning %s", velocity_results)
    return velocity_results


def issues(data: dict) -> dict[str, float]:
    """
    Returns information about issues, excluding pulls.

    Args:
        data (dict): Data containing repository information.
    Returns:
        dict[str, float]: Selected information about a repositories issue activities.

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    # filter_date = datetime.datetime.now(datetime.UTC)
    filter_date = datetime.date.today()
    issues_infos = {}
    issues_data = utils.date_filter(
        data["repository"]["issues"]["edges"],
        lambda x: x["node"]["updatedAt"],
        # datetime.timedelta(days=30 * 3),
        relativedelta(months=3),
    )
    # issues_data = base_data.get("issue")
    # issue_comments = data.get("issue_comments")
    # repository_data = base_data.get("repository")
    # if repository_data and issues_data and issue_comments:
    # log.info("Data available. Starting calculation...")
    # for repo in repository_data:
    # data = issues_data.get(repo)
    closed_issues = 0
    open_issues = 0
    total_issues = 0
    issue_close_times = []
    issue_first_response_times = []
    issue_creation_times = []
    issues_created_since = []
    comment_count_list = []
    ratio_open = None
    ratio_closed = None
    new_ratio = None
    avg_issue_comments = None
    avg_first_response_time_days = None
    avg_date_diff = None
    average_per_week = None
    # if data:
    for issue in issues_data:
        # graphql does NOT include pull requests in issue endpoint
        # pull_request_id = issue["node"]["closedByPullRequestsReferences"]["totalCount"]
        # is_pull_request = bool(pull_request_id)
        # if not is_pull_request:
        total_issues += 1
        state = issue["node"]["state"]
        issue_created_at = issue["node"]["createdAt"]
        issue_created_at = datetime.datetime.strptime(issue_created_at, "%Y-%m-%dT%H:%M:%SZ")
        if isinstance(issue_created_at, datetime.datetime):
            issue_created_at = issue_created_at.date()
        if issue_created_at >= (filter_date - relativedelta(months=3)):
            issues_created_since.append(issue_created_at)
        issue_creation_times.append(issue_created_at)
        issue_number = issue["node"]["number"]
        # Issue comments are only counted if comments have an id
        # Comments without an id are not created by an user
        total_comments = 0
        # issue_comments_repo = issue_comments.get(repo)
        first_response_time = None
        # if issue_comments_repo:
        # comments = issue_comments_repo.get(str(issue_number))
        comments = utils.date_filter(
            data["repository"]["issue" + str(issue_number)]["comments"]["edges"],
            lambda x: x["node"]["updatedAt"],
            # datetime.timedelta(days=30 * 3),
            relativedelta(months=3),
        )
        if comments:
            for comment in comments:
                comment_id = comment["node"]["id"]
                if comment_id:
                    total_comments += 1
            comment_count_list.append(total_comments)
            # first_comment_date = issue_comments.get(
            #     repo).get(issue_number)[0].get("created_at")
            first_comment_date = comments[-1]["node"]["createdAt"]
            if first_comment_date:
                first_comment_date = datetime.datetime.strptime(
                    first_comment_date, "%Y-%m-%dT%H:%M:%SZ"
                )
                if isinstance(first_comment_date, datetime.datetime):
                    first_comment_date = first_comment_date.date()
                first_response_time = first_comment_date - issue_created_at
                first_response_time = first_response_time.days
                issue_first_response_times.append(first_response_time)
            # Count states
            if state.lower() == "open":
                open_issues += 1
            if state.lower() in "closed":
                closed_issues += 1
                # closed_at = issue.get("closed_at")
                closed_at = issue["node"]["closedAt"]
                if closed_at:
                    closed_at = datetime.datetime.strptime(closed_at, "%Y-%m-%dT%H:%M:%SZ")
                    if isinstance(closed_at, datetime.datetime):
                        closed_at = closed_at.date()
                date_diff = closed_at - issue_created_at
                issue_close_times.append(date_diff.days)
    if len(issue_creation_times) > 1:
        # Sort the datetime list
        issue_creation_times.sort()
        earliest_date = issue_creation_times[0]
        if isinstance(earliest_date, datetime.datetime):
            earliest_date = earliest_date.date()
        latest_date = issue_creation_times[-1]
        if isinstance(latest_date, datetime.datetime):
            latest_date = latest_date.date()
        num_weeks = (latest_date - earliest_date).days // 7 + 1
        # Count the number of elements per week
        elements_per_week = [0] * num_weeks
        for issue_datetime in issue_creation_times:
            if isinstance(issue_datetime, datetime.datetime):
                issue_datetime = issue_datetime.date()
            week_index = (issue_datetime - earliest_date).days // 7
            elements_per_week[week_index] += 1
        average_per_week = round(statistics.fmean(elements_per_week))
    if issue_close_times:
        avg_date_diff = round(statistics.fmean(issue_close_times))
    if issue_first_response_times:
        # print(issue_first_response_times)
        avg_first_response_time_days = round(statistics.fmean(issue_first_response_times))
    if comment_count_list:
        avg_issue_comments = round(statistics.fmean(comment_count_list))
    if total_issues:
        ratio_open = (open_issues / total_issues) * 100
        ratio_closed = (closed_issues / total_issues) * 100
        new_ratio = (len(issues_created_since) / total_issues) * 100

    issues_infos = {
        "total_issues": total_issues,
        "open_issues": open_issues,
        "closed_issues": closed_issues,
        "new_issues": len(issues_created_since),
        "new_ratio": new_ratio,
        "average_issues_created_per_week": average_per_week,
        "average_issue_comments": avg_issue_comments,
        "average_issue_resolving_days": avg_date_diff,
        "average_first_response_time_days": avg_first_response_time_days,
        "ratio_open_total": ratio_open,
        "ratio_closed_total": ratio_closed,
    }
    # else:
    #     log.info("No data available. Returning %s", issues_infos)

    return issues_infos


def support_rate(data: dict) -> float:
    """
    The support rate uses issues and pulls which received a response
    in the last 6 months. Pulls are excluded from the issues
    (bc. pulls are also included in queried issues data).

    Args:
        data: Data object, required to gather data of already selected repositories.

    Returns:
        float: Support rate for selected repo.

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    # support_rate_results = {}
    # All issues required to get information about pulls in issue data
    # issues_data = utils.date_filter(
    #     data["repository"]["issues"]["edges"],
    #     lambda x: x["node"]["updatedAt"],
    #     # datetime.timedelta(days=30 * 3),
    #     relativedelta(months=3),
    # )
    issues = utils.date_filter(
        data["repository"]["issues"]["edges"],
        lambda x: x["node"]["updatedAt"],
        # datetime.timedelta(days=30 * 6),
        relativedelta(months=3),
    )
    pulls = utils.date_filter(
        data["repository"]["pullRequests"]["edges"],
        lambda x: x["node"]["updatedAt"],
        # datetime.timedelta(days=30 * 6),
        relativedelta(months=3),
    )
    # issues_pulls = base_data.get("issue")
    # issue_comments = base_data.get("issue_comments")
    # repository_data = base_data.get("repository")
    # if repository_data and issues_pulls and issue_comments:
    #     log.info("Data available. Starting calculation...")
    # for repo in repository_data:
    # data = issues_pulls.get(repo)
    # issue_flag = {}
    support_rate_val = None
    total_issues = len(issues)
    total_pulls = len(pulls)
    issues_with_response = 0
    pulls_with_response = 0
    # if data:
    for issue in issues:
        # pull_request_id = issue["node"]["closedByPullRequestsReferences"]["totalCount"]
        # is_pull_request = bool(pull_request_id)
        # # pull_request_id = issue.get("pull_request")
        # # is_pull_request = bool(pull_request_id)
        # # issue_number = issue.get("number")
        # issue_number = issue["node"]["number"]
        # issue_flag[str(issue_number)] = is_pull_request
        # if is_pull_request:
        #     total_pulls += 1
        # else:
        #     total_issues += 1
        # issue_comment_data = issue_comments.get(repo)
        comments = utils.date_filter(
            data["repository"]["issue" + str(issue["node"]["number"])]["comments"]["edges"],
            lambda x: x["node"]["updatedAt"],
            # datetime.timedelta(days=30 * 3),
            relativedelta(months=3),
        )
        # if issue_comment_data:
        # for issue, comments in issue_comment_data.items():
        # If issue is no pull
        # if not issue_flag.get(issue_number):
        # total_issues += 1
        if comments:
            # for comment in comments:
            issues_with_response += 1
            # break
        # else:
        # total_pulls += 1
    for pull in pulls:
        comments = utils.date_filter(
            data["repository"]["pull" + str(pull["node"]["number"])]["comments"]["edges"],
            lambda x: x["node"]["updatedAt"],
            # datetime.timedelta(days=30 * 3),
            relativedelta(months=3),
        )
        if comments:
            pulls_with_response += 1
            # for comment in comments:
            #     # comment_id = comment["node"]["id"]
            #     # if comment_id:
            #     pulls_with_response += 1
            #     break
    if total_issues > 0:
        issue_support = issues_with_response / total_issues
    else:
        issue_support = 0
    if total_pulls > 0:
        pulls_support = pulls_with_response / total_pulls
    else:
        pulls_support = 0
    support_rate_val = ((issue_support + pulls_support) / 2) * 100
    # support_rate_results = support_rate_val
    # else:
    #     log.info("No data available. Returning %s", support_rate_results)
    return support_rate_val


def security_advisories(data: dict) -> tuple[
    dict[str, Union[int, float, None]],
    dict[str, Union[int, float, str, bool]],
]:
    """
    Uses GitHub's security advisories to retrieve information and calculate
    basic scores.

    Args:
        base_data (dict): Data from GitHub's API

    Returns:
        tuple[dict[str, Union[int, float]], dict[str, str]] : Two dictionaries containing scores and
        raw information about security issues of the repositories with these vulnerabilities.

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    # repo_advisories = base_data.get("advisories")
    # repository_data = base_data.get("repository")
    # advisory_infos = {}
    # advisory_scores = {}
    # if repository_data and repo_advisories:
    #     log.info("Data available. Starting calculation...")
    #     for repo in repository_data:
    advisory = data["advisories"]
    advisories_available = bool(advisory)
    advisories = {}
    vuln_patched = 0
    vuln_not_patched = 0
    cvss_scores = []
    closed_adv = 0
    severities = []
    scores = {}
    if advisory:
        for adv in advisory:
            # On GitHub, advisories can only be set to withdrawn
            # by contacting the support if the advisory was made in error.
            withdrawn_at = bool(adv.get("withdrawn_at"))
            if withdrawn_at:
                continue
            adv_id = adv.get("ghsa_id")
            cve_id = adv.get("cve_id")
            severity = adv.get("severity")  # low, medium, high, critical
            severities.append(severity)
            state = adv.get("state")  # triage, draf, published or closed
            if state == "closed":
                closed_adv += 1
            published_at = adv.get("published_at")
            cvss_score = adv.get("cvss").get("score")
            if not cvss_score:
                if cve_id:
                    # if no score was provided but an id is available,
                    # NVD is checked.
                    cvss_score = utils.get_nvds(cve_id)
            if cvss_score:
                cvss_scores.append(cvss_score)
            cwes = adv.get("cwes")
            vulnerabilities = adv.get("vulnerabilities")
            if vulnerabilities:
                for vul_dict in vulnerabilities:
                    # package_name = vul_dict.get("package").get("name")
                    package_patched = bool(vul_dict.get("patched_versions"))
                    if package_patched:
                        vuln_patched += 1
                    else:
                        vuln_not_patched += 1

            advisories[adv_id] = {
                "cve_id": cve_id,
                "severity": severity,
                "state": state,
                "published_at": published_at,
                "cvss_score": cvss_score,
                "cwes": cwes,
            }
        severity_high_count = severities.count("high")
        severity_critical_count = severities.count("critical")
        severity_high_critical_total = severity_high_count + severity_critical_count
        if severities:
            ratio_severity_high_crit = (severity_high_critical_total / len(severities)) * 100
        else:
            ratio_severity_high_crit = None
        if cvss_scores:
            mean_cvs_score = statistics.fmean(cvss_scores)
        else:
            mean_cvs_score = None
        total_vuln = vuln_patched + vuln_not_patched
        if total_vuln > 0:
            patch_ratio = (vuln_patched / total_vuln) * 100
        else:
            patch_ratio = None
        scores = {
            "advisories_available": advisories_available,
            "patch_ratio": patch_ratio,
            "closed_advisories": closed_adv,
            "average_cvss_score": mean_cvs_score,
            "ratio_severity_high_crit": ratio_severity_high_crit,
        }
    # advisory_scores[repo] = scores
    # advisory_infos[repo] = advisories
    # else:
    #     log.info("No data available. Returning %s - %s", advisory_scores, advisory_infos)
    return scores, advisories


def contributions_distributions(data: dict) -> dict[str, Union[int, float]]:
    """
    Includes Bus Factor and Scores representing the Pareto Principle.

    Args:
        data (dict): Repository data.
    Returns:
        dict[str, Union[int, float]]: Information about the distribution of the contributions per
    contributors by calculating the bus factor and the pareto principle
    for each repository.

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    repo_pareto = {}
    commits_data = utils.date_filter(
        data["commits"],
        lambda x: x["committed_iso"],
        # datetime.timedelta(days=30 * 1),
        relativedelta(months=1),
    )
    # single_commits = base_data.get("single_commits")
    # repository_data = base_data.get("repository")
    # RoF metrics
    # if repository_data and single_commits and commits_data:
    #     log.info("Data available. Starting calculation...")
    #     for repo in repository_data:
    # commit_list = single_commits.get(repo)
    rof_pareto_tail = None
    rof_pareto_dominant = None
    rof_prot_diff = None
    avg_num_contributors_per_file = None
    rof_per_contributor = []
    if commits_data:
        file_committer = utils.get_contributor_per_files(commits_data)
        total_files = len(file_committer)
        num_contributors_per_files = []
        if file_committer:
            for committer_ids in file_committer.values():
                num_contributors_per_files.append(len(committer_ids))
            avg_num_contributors_per_file = statistics.fmean(num_contributors_per_files)
        else:
            avg_num_contributors_per_file = None
        committer_per_file = utils.invert_dict(file_committer)
        for contributor, files in committer_per_file.items():
            ratio_of_files = (len(files)) / total_files
            rof_per_contributor.append(ratio_of_files)

        rof_per_contributor.sort(reverse=True)
        total_file_contributions = sum(rof_per_contributor)
        total_file_contributer = len(rof_per_contributor)
        eighty_percent = total_file_contributions * 0.8
        running_contributions = 0
        rof_pareto_ist = 0
        rof_prot_diff = 0
        rof_pareto_ist_percentage = 0
        # Calculate the percentage of contributors which contribute
        # 80 % of the contributions
        for contrib, contributions in enumerate(rof_per_contributor, start=1):
            running_contributions += contributions
            # if contrib == math.ceil(twenty_percent):
            if running_contributions >= eighty_percent:
                rof_pareto_ist = contrib
                rof_pareto_ist_percentage = rof_pareto_ist / total_file_contributer
                break
        rof_pareto_dominant = rof_pareto_ist_percentage * 100
        rof_pareto_tail = 100 - rof_pareto_dominant
        rof_prot_diff = abs(20 - rof_pareto_dominant)
    pareto_results = {
        "RoF_tail": rof_pareto_tail,
        "RoF_dominant": rof_pareto_dominant,
        "RoF_diff_percent": rof_prot_diff,
        "avg_num_contributors_per_file": avg_num_contributors_per_file,
    }

    repo_pareto = pareto_results

    # NoC metrics
    # for repo in repository_data:
    # commits = commits_data.get(repo)
    total_committer = []
    no_committer = 0
    bus_factor_score = None
    noc_pareto_tail = None
    noc_pareto_dominant = None
    noc_prot_diff = None
    if commits_data:
        for commit in commits_data:
            contributor = None
            co_author = None
            # commit_elem = commit.get("commit")
            # if commit_elem:
            # verification = commit_elem.get("verification")
            # if verification:
            has_signature = commit.get("has_signature")
            if has_signature:
                committer = commit.get("author")
            else:
                committer = commit.get("committer")
            # else:
            #     committer = commit_elem.get("committer")
            if not committer:
                no_committer += 1
            else:
                contributor = committer.get("email")

            for elem in commit.get("co_authors"):
                total_committer.append(elem["email"])
            # message = commit.get("message")
            # co_author_line = re.findall(r"Co-authored-by:(.*?)>", message)
            # for value in co_author_line:
            #     co_author = value.split("<")[-1]
            #     total_committer.append(co_author)
            # else:
            #     log.debug("No commit: %s", commit)
            total_committer.append(contributor)
        committer_counter = collections.Counter(total_committer).values()
        commits_sorted = sorted(committer_counter, reverse=True)
        t_1 = sum(committer_counter) * 0.5
        t_2 = 0
        bus_factor_score = 0
        total_contributions = sum(commits_sorted)
        total_contributer = len(commits_sorted)
        eighty_percent = total_contributions * 0.8
        running_contributions = 0
        noc_pareto_ist = 0
        noc_prot_diff = 0
        noc_pareto_ist_percentage = 0
        # Calculate the percentage of contributors which contribute
        # 80 % of the contributions
        for contrib, contributions in enumerate(commits_sorted, start=1):
            running_contributions += contributions
            if running_contributions >= eighty_percent:
                noc_pareto_ist = contrib
                noc_pareto_ist_percentage = noc_pareto_ist / total_contributer
                break
            if t_2 <= t_1:
                t_2 += contributions
                bus_factor_score += 1
        noc_pareto_dominant = noc_pareto_ist_percentage * 100
        noc_pareto_tail = 100 - noc_pareto_dominant
        noc_prot_diff = abs(20 - noc_pareto_dominant)
    pareto_results = {
        "bus_factor_score": bus_factor_score,
        "NoC_tail": noc_pareto_tail,
        "NoC_dominant": noc_pareto_dominant,
        "NoC_diff_percent": noc_prot_diff,
    }
    # if repo in repo_pareto:
    repo_pareto.update(pareto_results)

    # else:
    #     log.info("No data available. Returning %s", repo_pareto)
    return repo_pareto


def number_of_support_contributors(data: dict) -> int:
    """
    Calculates the number of active contributors per repository

    Args:
        data (dict): Request object, required to gather data of already selected repositories.
    Returns:
        int: Score for the number of active contributors

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    # commits_data = data["commits"]
    # repository_data = base_data.get("repository")
    support_contributors = {}
    # if repository_data and commits_data:
    #     log.info("Data available. Starting calculation...")
    # for repo in repository_data:
    commits = utils.date_filter(
        data["commits"],
        lambda x: x["committed_iso"],
        # datetime.timedelta(days=30 * 6),
        relativedelta(months=6),
    )
    total_committer = set()
    score = 0
    if commits:
        for commit in commits:
            try:
                # committer_id = commit.get("committer").get("id")
                committer_id = commit.get("committer").get("email")
                total_committer.add(committer_id)
            except AttributeError:
                pass
        total_committer = len(total_committer)
        if total_committer < 5:
            score = 1
        elif total_committer >= 5 and total_committer <= 10:
            score = 2
        elif total_committer > 10 and total_committer <= 20:
            score = 3
        elif total_committer > 20 and total_committer <= 50:
            score = 4
        elif total_committer > 50:
            score = 5
    result_score = score / 5 * 100
    support_contributors = result_score
    # else:
    #     log.info("No data available. Returning %s", support_contributors)
    return support_contributors


def elephant_factor(data: dict) -> int:
    """
    Calculates the elephant factor (distribution of contributions
    by organizations user belong to) for each repository.

    Args:
        data (dict): Data object containing all necessary information
        about the repositories, contributors and organizations.

    Returns:
       int: Elephant factor

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    # users_data = base_data.get("organization_users")
    # repository_data = base_data.get("repository")
    # repo_elephant_factor = {}
    # if repository_data and contributor_data and users_data:
    #     log.info("Data available. Starting calculation...")
    #     for repo in repository_data:
    # contributors = contributor_data.get(repo)
    users_data = [
        user for user in data["organizations"] if "organizations" in data["organizations"][user]
    ]
    contributors = data["contributors"]["users"]
    elephant_factor_score = 0
    if contributors:
        org_contributions = {}
        user_contributions = {}
        for user in contributors:
            if isinstance(user, dict):
                login = user.get("login")
                contributions = user.get("contributions")
                user_contributions[login] = contributions
        # users = users_data.get(repo)
        if users_data:
            # for user, organizations in users.items():
            for elem in users_data:
                user = data["organizations"][elem]["login"]
                for organization in data["organizations"][elem]["organizations"]["nodes"]:
                    # if isinstance(organization, dict):
                    # if "login" in organization.keys():
                    org_name = organization.get("login")
                    user_contrib = user_contributions.get(user)
                    if org_name and user_contrib:
                        if org_name in org_contributions:
                            org_contributions[org_name] += user_contrib
                        else:
                            org_contributions[org_name] = user_contrib
                # else:
                #     if "login" in organizations.keys():
                #         org_name = organizations.get("login")
                #         user_contrib = user_contributions.get(user)
                #         if org_name and user_contrib:
                #             if org_name in org_contributions:
                #                 org_contributions[org_name] += user_contrib
                #             else:
                #                 org_contributions[org_name] = user_contrib
            t_1 = sum(org_contributions.values()) * 0.5
            t_2 = 0
            orgs_sorted = sorted(org_contributions.values(), reverse=True)
            for org_count in orgs_sorted:
                if isinstance(org_count, int) and t_2 <= t_1:
                    t_2 += org_count
                    elephant_factor_score += 1
    # repo_elephant_factor = elephant_factor_score
    # else:
    #     log.info("No data available. Returning %s", repo_elephant_factor)
    return elephant_factor_score


def size_of_community(data: dict) -> float:
    """
    The size of community includes contributors and subscribers.

    Args:
        data (dict): Request object, required to gather data
        of already selected repositories.

    Returns:
        float: Size of community score.

    Note:
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    # repo_community = {}
    # repository_data = base_data.get("repository")
    contributors_data = data["contributors"]["users"]
    contributor_count = utils.get_contributors(contributors_data, check_contrib=False)
    # if repository_data:
    # log.info("Data available. Starting calculation...")
    # for repo, data in repository_data.items():
    score = 0
    # subscribers_count = data.get("subscribers_count")

    # rest api is a bit weird about that
    # stargazer_count is the amount of user that starred the repo
    # watchers_count is the same as stargazer_count (!NOT amount of watchers!)
    # subscribers_count is the number of user that watch the repository
    # graphql api fixed that, stargazers ar stargazers and watchers are watchers
    subscribers_count = data["repository"]["watchers"]["totalCount"]
    # cont_count = contributor_count.get(repo)
    community_count = subscribers_count + contributor_count
    if community_count < 50:
        score = 1
    elif community_count >= 50 and community_count <= 100:
        score = 2
    elif community_count > 100 and community_count <= 200:
        score = 3
    elif community_count > 200 and community_count <= 300:
        score = 4
    elif community_count > 300:
        score = 5
    community_score = (score / 5) * 100
    # repo_community[repo] = community_score
    # else:
    #     log.info("No data available. Returning %s", repo_community)
    return community_score


def branch_lifecycle(data: dict) -> dict:
    """
    Calculate the branch lifecycle metrics for a repository.
    The metrics are based on the number of branches, their age and their age distribution.

    Args:
        data (dict): Data object containing repository branch information.

    Returns:
        dict: A dictionary containing the branch lifecycle metrics.

    Note:
        avg datediff has less information value if last created branch
        was created years ago.
        Original author: Jacqueline Schmatz, modified by: Tobias Dam
    """
    filter_date = datetime.datetime.now(datetime.UTC)
    # stale_branch_states = base_data.get("stale_branches")
    # active_branch_states = base_data.get("active_branches")
    # branches_data = base_data.get("branches")

    branches_data = data["repository"]["branches"]["edges"]
    active_branch_states = utils.get_active_branches(branches_data)
    stale_branch_states = utils.get_stale_branches(branches_data)
    # repository_data = base_data.get("repository")
    branch_results = {}
    # if repository_data and branches_data:
    #     log.info("Data available. Starting calculation...")
    #     for repo in repository_data:
    # branches = branches_data.get(repo)
    branch_creation_frequency_days = None
    branch_avg_age_days = None
    stale_ratio = None
    active_ratio = None
    unresolved_ratio = None
    resolved_ratio = None
    branch_state_counter = None
    if branches_data:
        dates = []
        open_dates = []
        all_branches = {}
        total_stale = 0
        total_active = 0
        if stale_branch_states:
            total_stale = len(stale_branch_states)
            all_branches.update(stale_branch_states)
        if active_branch_states:
            total_active = len(active_branch_states)
            all_branches.update(active_branch_states)
        total_branches = len(all_branches)
        branch_state_counter = collections.Counter(all_branches.values())
        # for branch, elements in branches.items():
        for branch in branches_data:
            # elem = elements[0]
            if branch["branch"]["name"] not in ("master", "main"):
                commit = branch["branch"].get("commit")
                if commit:
                    commit_date = commit.get("author").get("date")
                    commit_date = datetime.datetime.fromisoformat(commit_date)
                    if isinstance(commit_date, datetime.datetime):
                        commit_date = commit_date.date()
                else:
                    continue
                dates.append(commit_date)
                branch_state = all_branches.get(branch["branch"]["name"])
                if branch_state.lower() not in ["closed", "merged"]:
                    open_dates.append(commit_date)

        if total_branches > 0:
            total_merged = branch_state_counter["merged"]
            # total_compare = branch_state_counter["compare"] # state does not exist in graphql
            # https://docs.github.com/en/graphql/reference/enums#pullrequeststate
            total_open = branch_state_counter["open"]
            total_closed = branch_state_counter["closed"]
            total_nostate = branch_state_counter[""]
            # Calculations
            stale_ratio = (total_stale / total_branches) * 100
            active_ratio = (total_active / total_branches) * 100
            unresolved_total = total_open + total_nostate
            resolved_total = total_closed + total_merged
            unresolved_ratio = (unresolved_total / total_branches) * 100
            resolved_ratio = (resolved_total / total_branches) * 100
        else:
            stale_ratio = None
            active_ratio = None
            unresolved_ratio = None
            resolved_ratio = None

        # Calculating time metrics
        dates.sort()
        total_dates = len(dates)
        time_difference = datetime.timedelta(0)
        if isinstance(time_difference, datetime.datetime):
            time_difference = time_difference.date()
        time_diff_till_today = datetime.timedelta(0)
        # Ensure datatype is date instead of datetime
        if isinstance(time_diff_till_today, datetime.datetime):
            time_diff_till_today = time_diff_till_today.date()
        if isinstance(filter_date, datetime.datetime):
            filter_date = filter_date.date()
        # Calculate age for each date
        for open_date in open_dates:
            time_diff_till_today += filter_date - open_date
        counter = 0
        for i in range(1, len(dates), 1):
            counter += 1
            time_difference += dates[i] - dates[i - 1]
        # Time frequencies are only considered to be valid
        # when at least 2 values exist
        if total_dates > 1 and len(open_dates) > 0:
            branch_avg_age = time_diff_till_today / len(open_dates)
            branch_avg_age_days = branch_avg_age.days
            branch_creation_frequency = time_difference / counter
            branch_creation_frequency_days = branch_creation_frequency.days
        else:
            branch_avg_age_days = None
            branch_creation_frequency_days = None
    branch_results = {
        "branch_creation_frequency_days": branch_creation_frequency_days,
        "branch_avg_age_days": branch_avg_age_days,
        "stale_ratio": stale_ratio,
        "active_ratio": active_ratio,
        "unresolved_ratio": unresolved_ratio,
        "resolved_ratio": resolved_ratio,
        "branch_state_counter": branch_state_counter,
    }
    # else:
    #     log.info("No data available. Returning %s", branch_results)
    return branch_results
