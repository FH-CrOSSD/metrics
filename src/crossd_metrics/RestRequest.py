import json
import os
import queue
from abc import abstractmethod
from typing import Self, override

import github  # type: ignore[import]
from crossd_metrics.Request import Request
from crossd_metrics.utils import handle_rate_limit
from github import Auth, Github
from crossd_metrics.TokenPool import TokenPool  # type: ignore[import]
from rich.console import Console


class RestRequest(Request):
    """Retrieves information about a GitHub repository via the REST API."""

    __LOG_PREFIX = "[medium_purple bold][RestRequest][/medium_purple bold]"

    @override
    @abstractmethod
    def __init__(self, **kwargs):
        """Initializes the RestRequest object."""
        super(RestRequest, self).__init__(**kwargs)

        # use an access token for REST API requests
        auth = None
        try:
            auth = TokenPool(json.loads(os.environ.get("GH_TOKEN_LIST")))
        except TypeError:
            auth = Auth.Token(os.environ.get("GH_TOKEN").strip())

        # for github REST API
        self.gh = Github(auth=auth, per_page=100)
        # indicates whether to keep running
        self.keep_running = False
        # stores tasks regarding the github rest api
        self._rest = queue.Queue()
        # self.console = Console(force_terminal=False)
        self.console = Console()

    @property
    def rest(self) -> queue.Queue:
        """Get rest task queue."""
        return self._rest

    @override
    @abstractmethod
    def ask_all(self) -> Self:
        """Queue all tasks to be performed on the GitHub repository."""
        pass

    @override
    @abstractmethod
    def execute(self, rate_limit: bool = False) -> dict:
        """Execute the queued tasks via the REST API. Handles rate limits if necessary.

        Args:
          rate_limit: bool: whether to check rate limit (Default value = False)

        Returns:
            dict: The data retrieved by the executed tasks.
        Raises:
            github.RateLimitExceededException: If the rate limit is exceeded.
        """
        try:
            return self.__execute(rate_limit)
        except github.RateLimitExceededException as rlee:
            # If the rate limit is exceeded, handle it
            if rlee.status in [403, 429]:
                return handle_rate_limit(
                    rlee.headers["x-ratelimit-reset"],
                    self.__execute,
                )
            else:
                # If it's not a rate limit issue, raise the exception
                raise rlee

    def __execute(self, rate_limit: bool) -> dict:
        """Execute the queued tasks via the REST API. Handles rate limits if necessary.

        Args:
          rate_limit: bool: whether to check rate limit

        Returns:
            dict: The data retrieved by the executed tasks.
        """
        # Stores the merged data from all tasks
        rest_res = []
        self.console.log(f"{self.__LOG_PREFIX} Starting with rest tasks")
        try:
            # Process each item in the queue
            while item := self.rest.get():
                self.console.log(f"{self.__LOG_PREFIX} Executing {item.__qualname__}")
                rest_res.append(item())
                # Mark the task as done
                self.rest.task_done()
                self.console.log(f"{self.__LOG_PREFIX} Finished {item.__qualname__}")
                # Check if the queue is empty and stop if should not keep running
                if not self.keep_running and self.rest.empty():
                    break
        except queue.ShutDown:  # type: ignore[attr-defined]
            # Handle shutdown of the queue
            pass

        res = {}
        # Merge the results from all tasks
        for elem in rest_res:
            res.update(elem)
        if rate_limit:
            # If rate limit is requested, get the rate limit information
            tmp = self.gh.get_rate_limit()
            res.update({"rateLimit": {"core": tmp.core.raw_data, "search": tmp.search.raw_data}})
        self.console.log(f"{self.__LOG_PREFIX} Finished rest tasks")
        return res
