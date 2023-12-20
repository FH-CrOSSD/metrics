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
# res = (
#     Repository(owner="laurent22", name="Joplin")
#     .ask_all()
#     .execute(rate_limit=True, verbose=True)
# )

res = (
    Repository(owner="FH-CrOSSD", name="metrics")
    .ask_all()
    .execute(rate_limit=True, verbose=True)
)
console.log(res)
print(get_metrics(res))
# console.log(RepositoryOwner(login="numpy").ask_all().execute())
# console.log(Repository(owner="numpy",name="numpy").ask_funding_links().execute())

# json_res = json.dumps(res)

# open("test2.json", "w").write(json_res)

console.rule("Metrics")
# console.log(f"mean pull requests: {mean_pull_requests(json_res)}")
# console.log(f"median pull requests: {median_pull_requests(json_res)}")
# console.log(get_metrics(json.loads(open("test.json").read())))

# print(User(login="sindresorhus").ask_all().execute())
# print(Organization(login="KeeWeb").ask_all().execute())
# print(RepositoryOwner(login="sindresorhus").ask_all().execute())
# print(RepositoryOwner(login="KeeWeb").ask_all().execute())

# Exceptions:
# TimeoutError: The read operation timed out
# urllib3.exceptions.ReadTimeoutError: HTTPSConnectionPool(host='api.github.com', port=443): Read timed out. (read timeout=15)
# requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='api.github.com', port=443): Read timed out. (read timeout=15)
# gql.transport.exceptions.TransportQueryError: {'path': ['repository', 'dependencyGraphManifests'], 'locations': [{'line': 3, 'column': 5}], 'message': 'timedout'}

# Repo private
# Traceback (most recent call last):
#   File "/home/tdam/fh/projects/crossd/metrics/src/crossd_metrics/main.py", line 34, in <module>
#     Repository(owner="FH-CrOSSD", name="metrics")
#   File "/home/tdam/fh/projects/crossd/metrics/src/crossd_metrics/Repository.py", line 340, in execute
#     self.result = graph.result() | crawl.result() | rest.result()
#   File "/usr/lib/python3.10/concurrent/futures/_base.py", line 451, in result
#     return self.__get_result()
#   File "/usr/lib/python3.10/concurrent/futures/_base.py", line 403, in __get_result
#     raise self._exception
#   File "/usr/lib/python3.10/concurrent/futures/thread.py", line 58, in run
#     result = self.fn(*self.args, **self.kwargs)
#   File "/home/tdam/fh/projects/crossd/metrics/src/crossd_metrics/Repository.py", line 407, in _execute_crawl
#     return self._execute_sequence(self.crawl)
#   File "/home/tdam/fh/projects/crossd/metrics/src/crossd_metrics/Repository.py", line 413, in _execute_sequence
#     rest_res = [elem() for elem in seq]
#   File "/home/tdam/fh/projects/crossd/metrics/src/crossd_metrics/Repository.py", line 413, in <listcomp>
#     rest_res = [elem() for elem in seq]
#   File "/home/tdam/fh/projects/crossd/metrics/src/crossd_metrics/Repository.py", line 163, in _get_dependents
#     urllib.request.urlopen(
#   File "/usr/lib/python3.10/urllib/request.py", line 216, in urlopen
#     return opener.open(url, data, timeout)
#   File "/usr/lib/python3.10/urllib/request.py", line 525, in open
#     response = meth(req, response)
#   File "/usr/lib/python3.10/urllib/request.py", line 634, in http_response
#     response = self.parent.error(
#   File "/usr/lib/python3.10/urllib/request.py", line 563, in error
#     return self._call_chain(*args)
#   File "/usr/lib/python3.10/urllib/request.py", line 496, in _call_chain
#     result = func(*args)
#   File "/usr/lib/python3.10/urllib/request.py", line 643, in http_error_default
#     raise HTTPError(req.full_url, code, msg, hdrs, fp)
# urllib.error.HTTPError: HTTP Error 404: Not Found