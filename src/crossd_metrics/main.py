#!/usr/bin/env python3
# -*- coding=utf-8 -*-

from crossd_metrics.metrics import get_metrics, dependency_count
from crossd_metrics.Repository import Repository
from crossd_metrics.User import User
from crossd_metrics.MultiUser import MultiUser
from rich.console import Console
import json

console = Console(force_terminal=True)
console.rule("Data Retrieval")

res = (
    # Repository(owner="vercel", name="next.js")
    # Repository(owner="vercel", name="vercel")
    # Repository(owner="sveltejs", name="svelte")
    # Repository(owner="lorabridge2", name="bridge-automation-manager")
    Repository(owner="microsoft", name="vscode")
    # Repository(owner="FH-CrOSSD", name=".github")
    .ask_all()
    # .ask_releases_crawl()
    #
    # MultiUser(login=["tobiasdam","laurent22"])
    # .get_organizations()
    # Repository(owner="microsoft", name="vscode")
    #     .ask_contributors()
    # .ask_commits_clone()
    #     # # .ask_commit_files()
    #     # # .ask_commit_details(
    #     # #     "99ee73df36c01dac3a6615edcebee8de2271fd64"
    #     # # )
    #     # # Repository(owner="silvncr", name="silvncr")
    #     # .ask_dependents()
    #     # .ask_community_profile()
    # .ask_security_advisories(orderBy="published")
    # .ask_forks()
    # .ask_commits()
    #     # .ask_dependencies_sbom()
    #     # # .ask_dependencies_crawl()
    #     # # # Repository(owner="lorabridge2", name="bridge-automation-manager")
    #     # # # Repository(owner="lorabridge2", name="gateway-flow-manager")
    #     # .ask_identifiers()
    #     # .ask_license()
    #     # .ask_funding_links()
    #     # .ask_dates()
    #     # .ask_subscribers()
    #     # .ask_security_policy()
    #     # # # .ask_dependencies_sbom()
    #     # # # .ask_dependencies()
    # .ask_branches()
    #     # .ask_contributing()
    #     # .ask_closed_feature_requests()
    # .ask_feature_requests()
    #     # # # .ask_dependents()
    #     # .ask_releases2()
    # .ask_issues()
    # .ask_pull_requests()
    #     # .ask_readme()
    #     # .ask_workflow_runs()
    #     # .ask_workflows()
    #     # .ask_description()
    # User("laurent22").ask_organizations()
    .execute(rate_limit=True, verbose=True)
)
# open(res["repository"]["name"]+".json", "w").write(json.dumps(res))


# res = json.loads(open("test.json").read())
# orgs = []

# for user in res["contributors"]["users"]:
#     if user["login"] != "dependabot[bot]":
#         print(user["login"])
#         orgs.append(User(user["login"]).ask_organizations().execute())

# res["contributors"]["user_organizations"] = orgs
# tmp = (
#     MultiUser(
#         login=[
#             user["login"]
#             for user in res["contributors"]["users"]
#             if user["login"] != "dependabot[bot]"
#         ]
#     )
#     .get_organizations()
#     .execute(rate_limit=True, verbose=True)
# )
# console.log(res)
# console.log(tmp)
# console.log(orgs)
# open("test.json", "w").write(json.dumps(res))
# console.rule("Metrics")
# print(get_metrics(res))
# print(dependency_count(res))
