# -*- coding=utf-8 -*-
import queue
import tempfile
import urllib.error
from abc import abstractmethod
from typing import Self, override

from crossd_metrics.Request import Request
from crossd_metrics.utils import handle_rate_limit
from git import Repo  # type: ignore[import]
from rich.console import Console

# from rich.console import Console


class CloneRequest(Request):
    """Clones a Github repository and performs the queued actions on that repo."""

    __LOG_PREFIX = "[magenta bold][CloneRequest][/magenta bold]"

    @override
    @abstractmethod
    def __init__(self, owner: str, name: str, **kwargs):
        """
        Initializes the CloneRequest object.

        Args:
          owner: str: Github repository owner
          name: str: Github repository name
          **kwargs:

        """
        super(CloneRequest, self).__init__(**kwargs)

        # store tasks to be performed on the cloned repository
        self._clone: queue.Queue = queue.Queue()  # mypy need typp explictly
        # indicates whether to keep running
        self.keep_running = False
        # store the owner and name of the repository
        self.owner = owner
        self.name = name
        self.clone_opts = {}
        self.console = Console()
        # rich object for logging
        # self.console = Console(force_terminal=True)
        # store the cloned repository object
        self.repo: Repo

    @property
    def clone(self) -> queue.Queue:
        """Get clone task queue."""
        return self._clone

    @override
    @abstractmethod
    def ask_all(self) -> Self:
        """Queue all tasks to be performed on the cloned repository."""
        # To be implemented in subclasses
        # This method should define the tasks to be performed on the cloned repository.
        pass

    @override
    @abstractmethod
    def execute(self) -> dict:
        """
        Execute the queued tasks on the cloned repository. Handles rate limits if necessary.

        Returns:
          dict: The data retrieved by the executed tasks.
        Raises:
            urllib.error.HTTPError: If an HTTP error occurs during the execution.
        """
        try:
            # Use name mangled method to calling overridden method
            # in the subclass
            return self.__execute()
        except urllib.error.HTTPError as httpe:
            if httpe.status in [403, 429]:
                return handle_rate_limit(
                    httpe.headers["x-ratelimit-reset"],
                    self.__execute,
                )
            else:
                raise httpe

    def __execute(self) -> dict:
        """
        Execute the queued tasks on the cloned repository.

        Returns:
          dict: The data retrieved by the executed tasks.
        """
        # Store the merged result data
        res = {}
        # store the results of the tasks
        clone_res = []
        if not self.clone.empty():
            self.console.log(f"{self.__LOG_PREFIX} Starting with local git tasks")
            # Creates a temporary directory to clone the repository
            # and deletes it after use
            with tempfile.TemporaryDirectory(delete=True) as tempdir:
                # with self.console.status("Cloning repository"):
                self.console.log(f"{self.__LOG_PREFIX} Start cloning repository")
                self.repo = Repo.clone_from(
                    f"https://github.com/{self.owner}/{self.name}.git", tempdir, **self.clone_opts
                )
                self.console.log(f"{self.__LOG_PREFIX} Finished cloning repository")
                try:
                    while item := self.clone.get():
                        # Execute the task and store the result
                        self.console.log(f"{self.__LOG_PREFIX} Executing {item.__qualname__}")
                        clone_res.append(item())
                        # Mark the task as done
                        self.clone.task_done()
                        self.console.log(f"{self.__LOG_PREFIX} Finished {item.__qualname__}")
                        # Check if the queue is empty and if we should stop running
                        if not self.keep_running and self.clone.empty():
                            break
                except queue.ShutDown:  # type: ignore[attr-defined]
                    # Handle shutdown of the queue
                    pass
                # Merge the results from the tasks
                for elem in clone_res:
                    res.update(elem)
                # Clean up the repository object
                # This is important to avoid memory leaks
                # https://gitpython.readthedocs.io/en/stable/intro.html#leakage-of-system-resources
                self.repo.__del__()
                self.console.log(f"{self.__LOG_PREFIX} Finished local git tasks")
            return res
