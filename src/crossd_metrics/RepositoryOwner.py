from typing import Self, override

from crossd_metrics.Sponsorable import Sponsorable


class RepositoryOwner(Sponsorable):
    """Retrieves information about a GitHub repository owner."""

    @override
    def __init__(self, login: str):
        """
        Initializes the RepositoryOwner object.

        Args:
          login: str: Github repository owner username.
        """
        super(RepositoryOwner, self).__init__()
        self.query = self.ds.Query.repositoryOwner(login=login)

    @override
    def ask_all(self) -> Self:
        """Queue all tasks to be performed on the GitHub repository owner.

        Returns:
          Self: The current instance of the RepositoryOwner class.
        """
        return super().ask_all()
