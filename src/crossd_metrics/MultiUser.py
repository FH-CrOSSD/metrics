import re
import typing
from typing import Self, override

from crossd_metrics.User import User
from crossd_metrics.utils import simple_pagination
from gql.dsl import DSLQuery, dsl_gql  # type: ignore[import]


class MultiUser(User):
    """Retrieves information about multiple GitHub users."""

    @override
    def __init__(self, login: list[str]):
        """
        Initializes the MultiUser object.
        Args:
          login: list[str]: List of GitHub usernames

        """
        self.login = login  # type: ignore[assignment]
        super(User, self).__init__()

    @override
    def _reset_query(self) -> None:
        """
        Resets the query for each user.
        """
        self.query = {login: self.ds.Query.user(login=login) for login in self.login}

    @override
    def ask_all(self) -> Self:
        """Queue all tasks to be performed on the GitHub users.
        Returns:
          Self: The current instance of the MultiUser class.
        """
        return super().ask_all()

    @override
    def ask_organizations(self, after: typing.Optional[str] = None) -> Self:
        """Queues tasks to retrieve the organizations of each GitHub user.

        Returns:
            Self: The current instance of the MultiUser class.
        """
        for login in self.login:
            self._get_organizations(login)
        return self

    def _get_organizations(self, login: str, after: typing.Optional[str] = None) -> Self:
        """
        Prepares a grahql query to retrieves the organizations for a specific user.

        Args:
          login: str: Github username
          after: typing.Optional[str]: Graphql cursor for pagination (Default value = None)

        Returns:
            Self: The current instance of the MultiUser class.
        """
        # dependabot[bot] is returned by REST, but can not be found (and contains forbidden characters)
        # https://docs.github.com/en/enterprise-cloud@latest/admin/managing-iam/iam-configuration-reference/username-considerations-for-external-authentication#about-username-normalization
        # not allowed to start with number

        # use alias to replace forbidden characters
        self.query[login].alias(f"user_{re.sub(r"[\[\-\]]","_",login)}").select(
            self.ds.User.organizations(first=100, after=after).select(
                self.ds.OrganizationConnection.pageInfo.select(
                    self.ds.PageInfo.hasNextPage, self.ds.PageInfo.endCursor
                ),
                self.ds.OrganizationConnection.nodes.select(
                    self.ds.Organization.email,
                    self.ds.Organization.name,
                    self.ds.Organization.login,
                ),
            )
        )

        def tmp(self, after: typing.Optional[str] = None) -> None:
            """Helper function to handle pagination for getting organizations.

            Args:
              after: typing.Optional[str]: Graqhql cursore for pagination (Default value = None)
            """
            self._get_organizations(login, after)

        # add pagination check function to the list
        self.paginations.append(
            simple_pagination([f"user_{re.sub(r"[\[\-\]]","_",login)}", "organizations"], tmp)
        )
        return self

    def _GraphRequest__execute(self, rate_limit: bool) -> dict:
        """Override __execute method of GraphRequest class to execute the query for multiple users.

        Args:
          rate_limit: bool: Whether to check rate limits or not.

        Returns:
            dict: The data retrieved by the executed tasks.
        """
        # Get queries for each user
        query_parts = [*self.query.values()]
        if rate_limit:
            query_parts.append(self._RATELIMIT_QUERY)
        query = dsl_gql(DSLQuery(*query_parts))
        return self.client.execute(query)
