import re
from typing import Self, override
import typing
from crossd_metrics.Sponsorable import Sponsorable
from crossd_metrics.utils import simple_pagination


class User(Sponsorable):
    """Retrieves information about a GitHub user."""

    def __init__(self, login: str):
        """
        Initializes the User object.

        Args:
          login: str: github username
        """
        self.login = login
        super(User, self).__init__()

    @override
    def _reset_query(self) -> None:
        """Resets the gql query for the user."""
        self.query = self.ds.Query.user(login=self.login)

    @override
    def ask_all(self) -> Self:
        """Queue all tasks to be performed on the GitHub user.

        Returns:
          Self: The current instance of the User class.
        """
        return super().ask_all()

    def ask_organizations(self, after: typing.Optional[str] = None) -> Self:
        """
        Adds a query to retrieve the organizations of the GitHub user.
        This method uses pagination to retrieve all organizations.

        Args:
          after: typing.Optional[str]: Github cursor for pagination (Default value = None)

        Returns:
            Self: The current instance of the User class.
        """
        # dependabot[bot] is returned by REST, but can not be found (and contains forbidden characters)
        # https://docs.github.com/en/enterprise-cloud@latest/admin/managing-iam/iam-configuration-reference/username-considerations-for-external-authentication#about-username-normalization
        # not allowed to start with number

        # use alias to replace forbidden characters
        self.query.alias(f"user_{re.sub(r"[\[\-\]]","_",self.login)}").select(
            self.ds.User.login,
            self.ds.User.organizations(first=100, after=after).select(
                self.ds.OrganizationConnection.pageInfo.select(
                    self.ds.PageInfo.hasNextPage, self.ds.PageInfo.endCursor
                ),
                self.ds.OrganizationConnection.nodes.select(
                    self.ds.Organization.email,
                    self.ds.Organization.name,
                    self.ds.Organization.login,
                ),
            ),
        )

        # store method to check if there are more pages
        self.paginations.append(
            simple_pagination(
                [f"user_{re.sub(r"[\[\-\]]","_",self.login)}", "organizations"],
                self.ask_organizations,
            )
        )

        return self
