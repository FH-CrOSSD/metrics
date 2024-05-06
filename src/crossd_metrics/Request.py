from abc import ABC, abstractmethod
from typing import TypeVar

from crossd_metrics import client, ds
from gql.dsl import DSLQuery, dsl_gql

_Self = TypeVar("_Self", bound="Request")


class Request(ABC):
    """Defines basic methods for a GitHub graphql request."""

    _RATELIMIT_QUERY = ds.Query.rateLimit.select(
        ds.RateLimit.cost,
        ds.RateLimit.limit,
        ds.RateLimit.remaining,
        ds.RateLimit.resetAt,
        ds.RateLimit.nodeCount,
        ds.RateLimit.used,
    )

    @abstractmethod
    def __init__(self):
        super(Request, self).__init__()
        self.query = None

    @abstractmethod
    def ask_all(self) -> _Self:
        self.ask_dependencies().ask_funding_links().ask_security_policy().ask_contributing().ask_feature_requests().ask_closed_feature_requests()
        return self

    @abstractmethod
    def execute(self, rate_limit=False) -> dict:
        if not self.query.selection_set.selections:
            return {}

        query_parts = [self.query]
        if rate_limit:
            query_parts.append(self._RATELIMIT_QUERY)
        # query = dsl_gql(**operations)
        # query = dsl_gql(test1=operations["Repository"],test2=operations["RateLimit"])
        query = dsl_gql(DSLQuery(*query_parts))

        return client.execute(query)
