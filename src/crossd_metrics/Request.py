from abc import ABC, abstractmethod
from typing import Self


class Request(ABC):
    """Base class for all requests for retrieving information from GitHub."""

    @abstractmethod
    def __init__(self):
        """Initializes the Request object."""
        super(Request, self).__init__()

    @abstractmethod
    def ask_all(self) -> Self:
        """Queue all tasks to be performed on the GitHub object."""
        pass

    @abstractmethod
    def execute(self) -> dict:
        """Execute the queued tasks."""
        pass
