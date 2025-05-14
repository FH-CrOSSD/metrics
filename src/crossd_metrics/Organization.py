from typing import Self, override

from crossd_metrics.Sponsorable import Sponsorable


class Organization(Sponsorable):
    """Retrieves information about a GitHub organization."""

    @override
    def __init__(self, login: str):
        """Initializes the Organization object.

        Args:
          login: str: Github organization username.
        """
        super(Organization, self).__init__()
        self.query = self.ds.Query.organization(login=login)

    @override
    def ask_all(self) -> Self:
        """Queue all tasks to be performed on the GitHub organization.
        Returns:
          Self: The current instance of the Organization class.
        """
        return super().ask_all()
