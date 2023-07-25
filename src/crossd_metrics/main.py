#!/usr/bin/env python3
# -*- coding=utf-8 -*-

from crossd_metrics.Repository import Repository
from crossd_metrics.User import User
from crossd_metrics.Organization import Organization

# print(
#     Repository(owner="laurent22", name="Joplin").ask_funding_links().
#     ask_security_policy().ask_dependencies().ask_contributing().ask_feature_requests().ask_closed_feature_requests().ask_dependents().execute())

# print(
#     Repository(
#         owner="FH-CrOSSD",
#         name="crossd.tech").ask_pull_requests().execute(rate_limit=True))
res = Repository(owner="laurent22",
                 name="Joplin").ask_all().execute(rate_limit=True)
print(res)
import json

open("test.json", "w").write(json.dumps(res))

# print(User(login="sindresorhus").ask_all().execute())
# print(Organization(login="KeeWeb").ask_all().execute())