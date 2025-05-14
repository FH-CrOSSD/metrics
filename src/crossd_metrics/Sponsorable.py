from abc import abstractmethod
from typing import Self, override

from crossd_metrics.GraphRequest import GraphRequest
from gql.dsl import DSLInlineFragment # type: ignore[import]


class Sponsorable(GraphRequest):
    """Retrieves information about a GitHub object that can be sponsored."""

    @override
    @abstractmethod
    def __init__(self):
        """Initializes the Sponsorable object."""
        super(Sponsorable, self).__init__()

    def ask_sponsors(self) -> Self:
        """Adds a query to retrieve the number of sponsors of the GitHub object.

        Returns:
          Self: The current instance of the Sponsorable class.
        """
        fragment = DSLInlineFragment()
        fragment.on(self.ds.Sponsorable)
        fragment.select(
            self.ds.Sponsorable.hasSponsorsListing,
            self.ds.Sponsorable.sponsors(first=0).select(self.ds.SponsorConnection.totalCount),
        )
        self.query.select(fragment)
        return self

    @override
    @abstractmethod
    def ask_all(self) -> Self:
        """Queue all tasks to be performed on the GitHub object.

        Returns:
          Self: The current instance of the Sponsorable class.
        """
        return self.ask_sponsors()

    @override
    def execute(self, rate_limit: bool = False) -> dict:
        """Executes the queued tasks.

        Args:
          rate_limit: bool: whether to check rate limits (Default value = False)

        Returns:
            dict: The data retrieved by the executed tasks.
        """
        return super().execute(rate_limit)
