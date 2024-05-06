# -*- coding=utf-8 -*-
# exported symbols
__all__ = ["Repository", "User", "RepositoryOwner", "Organization"]
import os
from pathlib import Path

import crossd_metrics
from dotenv import load_dotenv
from github import Auth, Github
from gql import Client
from gql.dsl import DSLSchema
from gql.transport.requests import RequestsHTTPTransport

# read .env file
load_dotenv()

# create github graphql connection
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

# create graphql client, prove local graphql schema
client = Client(
    transport=transport,
    execute_timeout=100,
    schema=open(
        Path(crossd_metrics.__file__).parent.joinpath("schema.docs.graphql")
    ).read(),
)

ds = DSLSchema(client.schema)

# use an access token for REST API requests
auth = Auth.Token(os.environ.get("GH_TOKEN").strip())

# for github REST API
gh = Github(auth=auth, per_page=100)
