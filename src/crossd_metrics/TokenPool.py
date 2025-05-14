# -*- coding=utf-8 -*-
import random

from github import Auth  # type: ignore[import]


class TokenPool(Auth.Token):
    """Extends the PyGithub Auth.Token class to manage a pool of GitHub access tokens."""

    def __init__(self, token: list[str]):
        """Initializes the TokenPool object.
        This class is used to manage a pool of GitHub access tokens for authentication.

        Args:
          token: list[str]: List of GitHub access tokens to be used for authentication.
        """
        self._token = token

    @property
    def token(self) -> str:
        """Get a random token from the pool.

        Returns:
          str: A randomly selected GitHub access token from the pool.
        """
        tok = random.choice(self._token)
        # print(tok)
        return tok
