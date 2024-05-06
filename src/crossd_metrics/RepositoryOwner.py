from typing import TypeVar

from crossd_metrics import ds
from crossd_metrics.Sponsorable import Sponsorable

_Self = TypeVar("_Self", bound="RepositoryOwner")


class RepositoryOwner(Sponsorable):
    """Class for retrieving information about a GitHub repository owner."""

    def __init__(self, login: str):
        super(RepositoryOwner, self).__init__()
        self.query = ds.Query.repositoryOwner(login=login)

    def ask_all(self) -> _Self:
        return super().ask_all()
