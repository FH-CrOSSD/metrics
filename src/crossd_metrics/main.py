#!/usr/bin/env python3
# -*- coding=utf-8 -*-

from crossd_metrics.metrics import get_metrics, dependency_count
from crossd_metrics.Repository import Repository
from crossd_metrics.User import User
from crossd_metrics.MultiUser import MultiUser
from crossd_metrics.utils import merge_dicts, get_past
from rich.console import Console
import json
from dateutil.relativedelta import relativedelta
import datetime

console = Console(force_terminal=True)
# console.rule("Data Retrieval")
owner = "torvalds"
name = "linux"
owner = "lorabridge2"
name = "bridge-automation-manager"
owner = "mongodb"
name = "mongodb-kubernetes"
owner = "docker"
name = "compose"
# owner = "llvm"
# name = "llvm-project"

commits_since = None
commits_since_clone = None
# old = json.loads(open("compose82_orgs.json").read())
# # commits_since = old["repository"]["defaultBranchRef"]["last_commit"]["history"]["edges"][0]["node"][
# #     "committedDate"
# # ]
# # # commits_cursor = old["repository"]["defaultBranchRef"]["last_commit"]["history"]["edges"][0][
# # #     "cursor"
# # # ]
# # commits_since = (
# #     datetime.datetime.fromisoformat(commits_since) + datetime.timedelta(seconds=1)
# # ).isoformat()
# try:
#     commits_since_clone = (
#         datetime.datetime.fromisoformat(old["commits"][0]["committed_iso"]) + datetime.timedelta(seconds=1)
#     ).isoformat()
# except KeyError:
#     pass
# # commits_cursor = "5e913db7480dd3bdd3b13af0ee3a5d5f9e21162c 52"
# # commits_cursor = "5e913db7480dd3bdd3b13af0ee3a5d5f9e21162c 200"
# # commits_since = "2025-01-21T09:08:53Z"
# commits_since = "2025-05-14T10:55:02Z"
# commits_since = "2025-05-14T10:55:03+00:00"
# commits_since = "2025-05-14T12:42:05Z"
# commits_since = "2025-05-14T12:42:06+00:00"
# commits_since = "2025-01-14T12:42:06+00:00"
# # commits_since = "2025-05-14T12:42:05.000001+00:00"
# print(commits_since)
# repo.ask_commits(
#     details=False,
#     diff=False,
#     since=commits_since,
# )  # before=commits_cursor)

# print(get_past(relativedelta(months=6)))
console.rule("commit count")
console.log("Retrieving commits count for the last 12 months")
repo = Repository(owner=owner, name=name)
# count_res = repo.ask_commits_count(get_past(relativedelta(months=12)).isoformat()).execute()
count_res = repo.ask_commits_count(commits_since_clone if commits_since_clone else get_past(relativedelta(months=12)).isoformat()).execute()
# print(count_res)
clone_opts = {
    "bare": True,
    "depth": count_res["repository"]["defaultBranchRef"]["last_commit"]["history"]["totalCount"],
    # "filter": "blob:none",
}
repo = Repository(owner=owner, name=name)

# repo.ask_commits_clone(datetime.datetime.fromisoformat(commits_since_clone))
# res = repo.execute(rate_limit=True, verbose=True)
# console.print(res)
# exit()

console.rule("retrieving data")
repo.ask_identifiers()
c_available = repo.contributors_available()
if c_available:
    repo.clone_opts = clone_opts
    repo.ask_contributors()
    repo.ask_commits_clone()
else:
    repo.ask_commits(details=False, diff=False, since=commits_since)
    # repo.ask_commits_clone(since=None)
    repo.ask_commits_clone()

(
    repo.ask_dependencies_sbom()
    # .ask_dependencies_crawl()
    # .ask_dependencies()
    .ask_funding_links()
    .ask_security_policy()
    .ask_contributing()
    .ask_feature_requests()
    .ask_closed_feature_requests()
    .ask_dependents()
    .ask_pull_requests()
    .ask_readme()
    .ask_workflows()
    .ask_identifiers()
    .ask_description()
    .ask_license()
    .ask_dates()
    .ask_subscribers()
    .ask_community_profile()
    .ask_contributors()
    .ask_releases()
    # .ask_releases_crawl()
    .ask_security_advisories()
    .ask_issues()
    .ask_forks()
    # .ask_workflow_runs()
    # .ask_dependabot_alerts()
    # .ask_commits_clone()
    # .ask_commits()
    # .ask_commit_files()
    # .ask_commit_details()
    .ask_branches()
)

res = repo.execute(rate_limit=True, verbose=True)

console.log("finished retrieving repo data")

console.rule("building contributors data")

if not c_available:
    users = dict()

    for commit in res["repository"]["defaultBranchRef"]["last_commit"]["history"]["edges"]:
        user = commit["node"]["author"]["user"]
        if not user:
            user = commit["node"]["committer"]["user"]
            if not user:
                continue
        if user["login"] not in users:
            users[user["login"]] = 0
        users[user["login"]] += 1
    res["contributors"] = {"users": [{"login": x, "contributions": users[x]} for x in users]}

# res = (
#     #     Repository(owner="vercel", name="next.js")
#     # Repository(owner="vercel", name="vercel")
#     #     # Repository(owner="sveltejs", name="svelte")
#     # Repository(owner="lorabridge2", name="bridge-automation-manager")
#     # Repository(owner=owner, name=name, clone_opts=clone_opts)
#     repo
#     #     # Repository(owner="FH-CrOSSD", name=".github")
#     # .ask_commits_clone().ask_identifiers()
#     # .ask_all()
#     # .ask_contributors()
#     .ask_commits(details=False, diff=False)
#     # .ask_readme()
#     # .ask_identifiers()
#     .execute(rate_limit=True, verbose=True)
# )
console.log("finished building contributors data")
console.log(res)
open(res["repository"]["name"] + "81.json", "w").write(json.dumps(res))
# exit()

# res = json.loads(open("vscode.json").read())

users = []
tmp = {}

# ~ 400 users failed quite often
# therefore split to requests of 200 users

# print(list(x["login"] for x in res["contributors"]["users"]))
# print(len(list(x["login"] for x in res["contributors"]["users"])))


console.rule("getting users")
for user in res["contributors"]["users"]:
    if "[bot]" not in user["login"]:
        users.append(user["login"])
    if len(users) % 200 == 0:
        tmp = merge_dicts(tmp, MultiUser(login=users).ask_organizations().execute(rate_limit=True))
        users = []
else:
    tmp = merge_dicts(tmp, MultiUser(login=users).ask_organizations().execute(rate_limit=True))
    console.log(f"finished users")


# often fails with http 502
# github graphql backends apparently often fails with 502 due to queries taking too long
# and some backends seems to have different timeouts, see DependencyGraphManifest
# tmp = (
#     MultiUser(
#         login=[
#             user["login"] for user in res["contributors"]["users"] if "[bot]" not in user["login"]
#         ]
#     )
#     .ask_organizations()
#     .execute(rate_limit=True)
# )
# console.log(res)
res["organizations"] = tmp
open(res["repository"]["name"] + "81_orgs.json", "w").write(json.dumps(res))
