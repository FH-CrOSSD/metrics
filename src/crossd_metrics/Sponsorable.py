from crossd_metrics import ds, client
from gql.dsl import dsl_gql, DSLQuery, DSLInlineFragment
from typing import TypeVar
from crossd_metrics.Request import Request
from abc import ABC, abstractmethod

_Self = TypeVar('_Self', bound='Sponsorable')


class Sponsorable(Request):
    """docstring for Sponsorable."""
    _RATELIMIT_QUERY = ds.Query.rateLimit.select(
        ds.RateLimit.cost, ds.RateLimit.limit, ds.RateLimit.remaining,
        ds.RateLimit.resetAt, ds.RateLimit.nodeCount, ds.RateLimit.used)

    @abstractmethod
    def __init__(self):
        super(Sponsorable, self).__init__()
        self.sponsorable = None

    def ask_sponsors(self) -> _Self:
        self.query.select(
            self.sponsorable.hasSponsorsListing,
            self.sponsorable.sponsors(first=0).select(
                ds.SponsorConnection.totalCount))
        return self

    @abstractmethod
    def ask_all(self) -> _Self:
        return self.ask_sponsors()

    def execute(self, rate_limit=False) -> dict:
        return super().execute(rate_limit)

    # def execute(self, rate_limit=False) -> dict:
    #     query_parts = [self.query]
    #     if rate_limit:
    #         query_parts.append(self._RATELIMIT_QUERY)
    #     # query = dsl_gql(**operations)
    #     # query = dsl_gql(test1=operations["Repository"],test2=operations["RateLimit"])
    #     query = dsl_gql(DSLQuery(*query_parts))

    #     return client.execute(query)


#   user(login: "laurent22") {
#     name
#     hasSponsorsListing,
#     sponsors(first:10) {
#       totalCount
#       nodes {
#         ... on User{
#         login}
#       }
#     }
#     monthlyEstimatedSponsorsIncomeInCents
#     sponsorsActivities(first: 10) {
#       nodes {
#         action
#       }
#     }
#   }
# }