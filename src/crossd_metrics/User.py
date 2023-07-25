from crossd_metrics import ds, client
from gql.dsl import dsl_gql, DSLQuery, DSLInlineFragment
from typing import TypeVar
from crossd_metrics.Sponsorable import Sponsorable

_Self = TypeVar('_Self', bound='User')


class User(Sponsorable):
    """docstring for Sponsorable."""

    def __init__(self, login: str):
        super(User, self).__init__()
        self.query = ds.Query.user(login=login)
        self.sponsorable = ds.User

    def ask_all(self) -> _Self:
        return super().ask_all()