#!/usr/bin/env python3
# -*- coding=utf-8 -*-

import json

from crossd_metrics.metrics import get_metrics, mean_pull_requests, median_pull_requests
from crossd_metrics.Organization import Organization
from crossd_metrics.Repository import Repository
from crossd_metrics.RepositoryOwner import RepositoryOwner
from crossd_metrics.User import User
from rich.console import Console

console = Console(force_terminal=True)
# print(
#     Repository(owner="laurent22", name="Joplin").ask_funding_links().
#     ask_security_policy().ask_dependencies().ask_contributing().ask_feature_requests().ask_closed_feature_requests().ask_dependents().execute())

# print(
#     Repository(
#         owner="FH-CrOSSD",
#         name="crossd.tech").ask_pull_requests().execute(rate_limit=True))

# print(json.dumps(Repository(
#         owner="FH-CrOSSD",
#         name="crossd.tech").ask_workflows().execute()))#.execute(rate_limit=True)
console.rule("Data Retrieval")
# res = Repository(owner="laurent22",
#                  name="Joplin").ask_all().execute(rate_limit=True,
#                                                   verbose=True)
# console.log(res)
# console.log(RepositoryOwner(login="numpy").ask_all().execute())
# console.log(Repository(owner="numpy",name="numpy").ask_funding_links().execute())

# json_res = json.dumps(res)

# open("test.json", "w").write(json_res)

console.rule("Metrics")
# console.log(f"mean pull requests: {mean_pull_requests(json_res)}")
# console.log(f"median pull requests: {median_pull_requests(json_res)}")
console.log(get_metrics(json.loads(open("test.json").read())))

# print(User(login="sindresorhus").ask_all().execute())
# print(Organization(login="KeeWeb").ask_all().execute())
# print(RepositoryOwner(login="sindresorhus").ask_all().execute())
# print(RepositoryOwner(login="KeeWeb").ask_all().execute())

# Exceptions:
# TimeoutError: The read operation timed out
# urllib3.exceptions.ReadTimeoutError: HTTPSConnectionPool(host='api.github.com', port=443): Read timed out. (read timeout=15)
# requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='api.github.com', port=443): Read timed out. (read timeout=15)
# gql.transport.exceptions.TransportQueryError: {'path': ['repository', 'dependencyGraphManifests'], 'locations': [{'line': 3, 'column': 5}], 'message': 'timedout'}
