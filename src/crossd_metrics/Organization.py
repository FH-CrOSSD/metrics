from crossd_metrics import ds, client
from gql.dsl import dsl_gql, DSLQuery, DSLInlineFragment
from typing import TypeVar
from crossd_metrics.Sponsorable import Sponsorable

_Self = TypeVar('_Self', bound='Organization')


class Organization(Sponsorable):
    """docstring for Sponsorable."""

    def __init__(self, login: str):
        super(Organization, self).__init__()
        self.query = ds.Query.organization(login=login)
        self.sponsorable = ds.Organization

    def ask_all(self) -> _Self:
        return super().ask_all()