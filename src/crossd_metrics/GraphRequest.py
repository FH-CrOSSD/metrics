import os
from abc import abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Self, override

import crossd_metrics
from crossd_metrics.constants import MAX_RETRIES_CHUNKED_ERROR
import gql  # type: ignore[import]
import gql.transport  # type: ignore[import]
import gql.transport.exceptions  # type: ignore[import]
from crossd_metrics.Request import Request
from crossd_metrics.utils import handle_rate_limit, merge_dicts
from gql import Client
from gql.dsl import DSLQuery, DSLSchema, DSLType, dsl_gql  # type: ignore[import]
from gql.transport.requests import RequestsHTTPTransport  # type: ignore[import]
from graphql import build_ast_schema, parse  # type: ignore[import]
import requests
from rich.progress import track
from rich.console import Console

class GraphRequest(Request):
    """Retrieves information about a GitHub repository via the GraphQL API."""

    # Load the GraphQL schema from a file
    # The schema is used to validate the GraphQL queries and responses
    _SCHEMA = open(Path(crossd_metrics.__file__).parent.joinpath("schema.docs.graphql")).read()
    # Parse the schema and build an AST schema
    ds = DSLSchema(build_ast_schema(parse(_SCHEMA)))

    # Define the GraphQL query part for rate limiting information
    _RATELIMIT_QUERY = ds.Query.rateLimit.select(
        ds.RateLimit.cost,
        ds.RateLimit.limit,
        ds.RateLimit.remaining,
        ds.RateLimit.resetAt,
        ds.RateLimit.nodeCount,
        ds.RateLimit.used,
    )

    __LOG_PREFIX = "[deep_pink3 bold][GraphRequest][/deep_pink3 bold]"

    @override
    @abstractmethod
    def __init__(self, **kwargs):
        """
        Initializes the GraphRequest object.
        """
        super(GraphRequest, self).__init__(**kwargs)
        # create github graphql connection
        self.transport = RequestsHTTPTransport(
            url="https://api.github.com/graphql",
            verify=True,
            retries=5,
            timeout=100,
            headers={
                "Authorization": f'bearer {os.environ.get("GH_TOKEN").strip()}',
                "Accept": "application/vnd.github.hawkgirl-preview+json",
            },
        )

        # create graphql client, provide local graphql schema
        self.client = Client(
            transport=self.transport,
            execute_timeout=100,
            schema=self._SCHEMA,
        )

        # store the gql query to be executed
        self._query: DSLType = None  # type: ignore
        # stores functions that are used check if paginations for a specific part are needed
        self._paginations: list[Callable] = []  # type: ignore
        # reset the query for reuse
        self._reset_query()
        # self.console = Console(force_terminal=True)
        self.console = Console()

    @abstractmethod
    def _reset_query(self) -> None:
        """Resets the query to its initial state."""
        # To be implemented in subclasses
        pass

    @property
    def query(self) -> DSLType:
        """Get the current GraphQL query.
        Returns:
          DSLType: The current GraphQL query.
        """
        return self._query

    @query.setter
    def query(self, query: DSLType) -> None:
        """Set the GraphQL query to be executed.
        Args:
          query (DSLType): The GraphQL query to be executed.
        """
        self._query = query

    @property
    def paginations(self) -> list[Callable]:
        """Get the list of pagination check functions.
        Returns:
          list[Callable]: The list of pagination functions.
        """
        return self._paginations

    @paginations.deleter
    def paginations(self) -> None:
        """Clear the list of pagination check functions."""
        self._paginations = []

    @abstractmethod
    def ask_all(self) -> Self:
        """Queue all tasks to be performed on the GraphQL API.
        Returns:
          Self: The current instance of the GraphRequest class.
        """
        # To be implemented in subclasses
        pass

    @abstractmethod
    def execute(self, rate_limit: bool = False) -> dict:
        """Execute the queued tasks via the GraphQL API.
        Handles rate limits if necessary.
        Args:
          rate_limit: bool: Whether to check rate limits or not.
        Returns:
          dict: The data retrieved by the executed tasks.
        """
        try:
            # Check if nothing was queued
            if not self.query.selection_set.selections:
                return {}
        except:
            pass

        self.console.log(f"{self.__LOG_PREFIX} Starting with graphql tasks")

        self.console.log(f"{self.__LOG_PREFIX} Querying first page")
        # Use name mangled method to avoid calling overridden method
        # execute the query
        result = self.__execute_page(rate_limit)
        self.console.log(f"{self.__LOG_PREFIX} Finished first page")
        page_count=1
        # Check if paginations are not needed
        if not self.paginations:
            self.console.log(f"{self.__LOG_PREFIX} No further pages")
            return result
        while True:
            # Do pages until all paginations are done
            # Reset query to prepare for the next page
            self._reset_query()
            # Store actual pagination methods
            methods = []
            page_checks = self.paginations
            # Reset pagination check method list
            # as it will store the methods for the next pagination
            del self.paginations
            # Execute the pagination checks
            # and store the methods that are needed for the next page
            for registered in page_checks:
                if tmp := registered(result):
                    if isinstance(tmp, list):
                        methods.extend(tmp)
                    else:
                        methods.append(tmp)

            # Check if there are no more methods to execute
            if not methods:
                break
            # Execute the methods that prepare the query for the next page
            for method in methods:
                # self.console.log(f"{self.__LOG_PREFIX} Queueing {method.__qualname__}")
                method()

            page_count += 1
            # Execute the query for the next page
            self.console.log(f"{self.__LOG_PREFIX} Querying page {page_count}")
            page = self.__execute_page(rate_limit)
            self.console.log(f"{self.__LOG_PREFIX} Finished page {page_count}")
            # Calculate the rate limit information for the whole query
            if rate_limit:
                page["rateLimit"]["cost"] += result["rateLimit"]["cost"]
                page["rateLimit"]["nodeCount"] += result["rateLimit"]["nodeCount"]
            # Merge the results of the current page with the previous results
            result = merge_dicts(result, page)
        self.console.log(f"{self.__LOG_PREFIX} Finished graphql tasks")
        return result

    def __execute(self, rate_limit: bool) -> dict:
        """Execute the GraphQL query.
        Args:
          rate_limit: bool: Whether to check rate limits or not.
        Returns:
          dict: The data retrieved by the executed tasks.
        """
        # Prepare and execute the GraphQL query request
        query_parts = [self.query]
        if rate_limit:
            query_parts.append(self._RATELIMIT_QUERY)
        query = dsl_gql(DSLQuery(*query_parts))
        return self.client.execute(query)

    def __execute_page(self, rate_limit: bool, tries: int = 0) -> dict:
        """Execute the GraphQL query for a specific page.
        Args:
          rate_limit: bool: Whether to check rate limits or not.
        Returns:
          dict: The data retrieved by the executed tasks.
        Raises:
          gql.transport.exceptions.TransportServerError: If a server error occurs during the request.
          gql.transport.exceptions.TransportQueryError: If a query error occurs during the request.
        """
        try:
            # Execute the GraphQL query
            return self.__execute(rate_limit)
        except requests.exceptions.ChunkedEncodingError as cee:
            print("cee")
            if tries < MAX_RETRIES_CHUNKED_ERROR:
                print("retry")
                return self.__execute_page(rate_limit, tries=tries + 1)
            else:
                raise cee
        except gql.transport.exceptions.TransportServerError as tse:
            # Check if the error is a rate limit error
            if tse.code in [403, 429]:
                # wait for the rate limit to reset
                print(tse)
                return handle_rate_limit(
                    self.transport.response_headers.get("x-ratelimit-reset"),
                    lambda: self.__execute(rate_limit),
                )
            else:
                # Raise other server errors
                raise tse
        except gql.transport.exceptions.TransportQueryError as tqe:
            # handling this error (dpendencyGraphManifest) is not necessary for the paginations as the connection uses a session
            # so if the Github loadbalancer assigns us to a host that can process our request
            # the paginations will also work as they are processed by the same host
            # (some hostsare configured with a lower request timeout, which is not sufficient for the dependencyGraphManifests requests)
            if (
                len(tqe.errors) == 1
                and "path" in tqe.errors[0]
                and tqe.errors[0]["path"] == ["repository", "dependencyGraphManifests"]
                and tqe.errors[0]["message"] == "timedout"
            ):
                # check if error is related to dependencyGraphManifests
                for i in track(
                    range(20),
                    description="Retrying due to timedout dependencyGraphManifests",
                ):
                    # retry 20 times
                    try:
                        return self.__execute(rate_limit)
                    except gql.transport.exceptions.TransportQueryError as tqe_inner:
                        if (
                            len(tqe_inner.errors) == 1
                            and tqe_inner.errors[0]["path"]
                            == ["repository", "dependencyGraphManifests"]
                            and tqe_inner.errors[0]["message"] == "timedout"
                        ):
                            # self.console.log("timedout dependencyGraphManifests")
                            # retry on dependencyGraphManifests error
                            pass
                        else:
                            # raise other errors
                            raise tqe_inner
                else:
                    # raise the error if the retry limit is reached
                    raise tqe
            else:
                # raise other errors
                raise tqe
