from abc import abstractmethod
from typing import TypeVar

from crossd_metrics import ds
from crossd_metrics.Request import Request
from gql.dsl import DSLInlineFragment

_Self = TypeVar("_Self", bound="Sponsorable")


class Sponsorable(Request):
    """Class for retrieving information about a GitHub sponsorable."""

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
        super(Sponsorable, self).__init__()

    def ask_sponsors(self) -> _Self:
        fragment = DSLInlineFragment()
        fragment.on(ds.Sponsorable)
        fragment.select(
            ds.Sponsorable.hasSponsorsListing,
            ds.Sponsorable.sponsors(first=0).select(ds.SponsorConnection.totalCount),
        )
        self.query.select(fragment)
        return self

    @abstractmethod
    def ask_all(self) -> _Self:
        return self.ask_sponsors()

    def execute(self, rate_limit=False) -> dict:
        return super().execute(rate_limit)
