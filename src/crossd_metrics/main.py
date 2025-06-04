#!/usr/bin/env python3
# -*- coding=utf-8 -*-

from crossd_metrics.metrics import get_metrics, dependency_count
from crossd_metrics.Repository import Repository
from crossd_metrics.User import User
from crossd_metrics.MultiUser import MultiUser
from crossd_metrics.utils import merge_dicts
from rich.console import Console
import json

console = Console(force_terminal=True)
console.rule("Data Retrieval")

res = (
#     Repository(owner="vercel", name="next.js")
#     # Repository(owner="vercel", name="vercel")
#     # Repository(owner="sveltejs", name="svelte")
    Repository(owner="lorabridge2", name="bridge-automation-manager")
#     # Repository(owner="microsoft", name="vscode")
#     # Repository(owner="FH-CrOSSD", name=".github")
    .ask_all()
    .execute(rate_limit=True, verbose=True)
)

# open(res["repository"]["name"]+".json", "w").write(json.dumps(res))

# res = json.loads(open("vscode.json").read())

users = []
tmp = {}

# ~ 400 users failed quite often
# therefore split to requests of 200 users

# print(list(x["login"] for x in res["contributors"]["users"]))
# print(len(list(x["login"] for x in res["contributors"]["users"])))

for user in res["contributors"]["users"]:
    if "[bot]" not in user["login"]:
        users.append(user["login"])
    if len(users) % 200 == 0:
        # print(users)
        # print(len(users))
        tmp = merge_dicts(tmp, MultiUser(login=users).ask_organizations().execute(rate_limit=True))
        users = []
else:
    tmp = merge_dicts(tmp, MultiUser(login=users).ask_organizations().execute(rate_limit=True))

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
console.log(res)
res["organizations"] = tmp
open(res["repository"]["name"] + "2_orgs.json", "w").write(json.dumps(res))
