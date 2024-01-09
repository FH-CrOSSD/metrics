# -*- coding=utf-8 -*-
__all__ = ["Repository", "User", "RepositoryOwner", "Organiuation"]
import os
import base64
from pathlib import Path

import crossd_metrics
from dotenv import load_dotenv
from github import Auth, Github
from gql import Client
from gql.dsl import DSLSchema
from gql.transport.requests import RequestsHTTPTransport

# from crossd_metrics.Repository import Repository

load_dotenv()
transport = RequestsHTTPTransport(
    url="https://api.github.com/graphql",
    verify=True,
    retries=3,
    timeout=100,
    headers={
        "Authorization": f'bearer {os.environ.get("GH_TOKEN").strip()}',
        "Accept": "application/vnd.github.hawkgirl-preview+json",
    },
)

client = Client(
    transport=transport,
    execute_timeout=100,
    # fetch_schema_from_transport=True,
    schema=open(
        Path(crossd_metrics.__file__).parent.joinpath("schema.docs.graphql")
    ).read(),
)

ds = DSLSchema(client.schema)


# Authentication is defined via github.Auth

# using an access token
auth = Auth.Token(base64.b64decode(os.environ.get("GH_TOKEN").strip()))

# First create a Github instance:

# Public Web Github
gh = Github(auth=auth, per_page=100)

# # Then play with your Github objects:
# for repo in g.get_user().get_repos():
#     print(repo.name)
