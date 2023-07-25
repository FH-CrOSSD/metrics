# -*- coding=utf-8 -*-
__all__ = ['Repository']
from gql import Client
from gql.transport.requests import RequestsHTTPTransport
from gql.dsl import DSLSchema
from dotenv import load_dotenv
import os
import crossd_metrics
from pathlib import Path
# from crossd_metrics.Repository import Repository

load_dotenv()
transport = RequestsHTTPTransport(
    url="https://api.github.com/graphql",
    verify=True,
    retries=3,
    timeout=100,
    headers={
        'Authorization': f'bearer {os.environ.get("GH_TOKEN")}',
        'Accept': 'application/vnd.github.hawkgirl-preview+json'
    })

client = Client(
    transport=transport,
    execute_timeout=100,
    # fetch_schema_from_transport=True,
    schema=open(
        Path(crossd_metrics.__file__).parent.joinpath(
            "schema.docs.graphql")).read())

ds = DSLSchema(client.schema)
