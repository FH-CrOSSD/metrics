# -*- coding=utf-8 -*-

import datetime
import json
import statistics

from crossd_metrics import constants, utils


def get_metrics(data: dict):
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
    }


def mean_pull_requests(data: dict) -> datetime.timedelta:
    diffs = _diff_pull_requests(data)
    return datetime.timedelta(
        seconds=statistics.mean(elem.total_seconds() for elem in diffs)
    )


def median_pull_requests(data: dict) -> datetime.timedelta:
    diffs = _diff_pull_requests(data)
    return statistics.median(diffs)


def _diff_pull_requests(data: dict) -> [datetime.datetime]:
    # data = json.loads(data)
    diffs = []
    for elem in data["repository"]["pullRequests"]["edges"]:
        diffs.append(
            datetime.datetime.strptime(elem["node"]["mergedAt"], "%Y-%m-%dT%H:%M:%S%z")
            - datetime.datetime.strptime(
                elem["node"]["createdAt"], "%Y-%m-%dT%H:%M:%S%z"
            )
        )
    return diffs


def dependents_count(data: dict) -> int:
    return data["dependents"]


def has_security_policy(data: dict) -> bool:
    return data["repository"]["isSecurityPolicyEnabled"]


def dependency_count(data: dict) -> int:
    return sum(
        elem["node"]["dependenciesCount"]
        for elem in data["repository"]["dependencyGraphManifests"]["edges"]
    )


def has_contributing_policy(data: dict) -> bool:
    return bool(
        data["repository"]["contributing_md"]
        or data["repository"]["contributing_txt"]
        or data["repository"]["contributing_raw"]
    )


def feature_request_count(data: dict) -> int:
    return data["repository"]["feature_requests"]["totalCount"]


def closed_feature_request_count(data: dict) -> int:
    return data["repository"]["closed_feature_requests"]["totalCount"]


def has_collaboration_platform(data: dict) -> bool:
    res = {"discord": [], "reddit": [], "slack": []}
    contents = [
        data["repository"][utils.get_readme_index(elem)] for elem in constants.readmes
    ]
    # print(contents)
    urls = []
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

    # return any(res['discord'], res['reddit'], res['slack'])
    # print(res)
    return any(res.values())


def uses_workflows(data: dict) -> bool:
    return any([wf["state"] == "active" for wf in data["workflows"]])
    # return len(data['workflow_runs']) > 0


def current_state_workflows(data: dict) -> dict:
    res = {}
    # for elem in data["workflow_runs"]:
    #     res.setdefault(
    #         elem["name"],
    #         {"created_at": elem["created_at"], "conclusion": elem["conclusion"]},
    #     )
    #     if elem["created_at"] > res[elem["name"]]["created_at"]:
    #         res[elem["name"]] = {
    #             "created_at": elem["created_at"],
    #             "conclusion": elem["conclusion"],
    #         }

    for elem in data["workflows"]:
        res.setdefault(
            elem["name"],
            {
                "created_at": elem["last_run"]["created_at"],
                "conclusion": elem["last_run"]["conclusion"],
            },
        )
        if elem["last_run"]["created_at"] > res[elem["name"]]["created_at"]:
            res[elem["name"]] = {
                "created_at": elem["last_run"]["created_at"],
                "conclusion": elem["last_run"]["conclusion"],
            }
    return res


def has_funding_links(data: dir) -> bool:
    return bool(data["repository"]["fundingLinks"])
