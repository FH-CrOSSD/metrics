import queue
import urllib.error
from abc import abstractmethod
from typing import Self, override

from crossd_metrics.Request import Request
from crossd_metrics.utils import handle_rate_limit
from rich.console import Console


class CrawlRequest(Request):
    """Retrieves information about a GitHub repository by crawling the github website."""

    __LOG_PREFIX = "[light_goldenrod3 bold][CrawlRequest][/light_goldenrod3 bold]"

    @override
    @abstractmethod
    def __init__(self, **kwargs):
        """
        Initializes the CrawlRequest object.
        """
        super(CrawlRequest, self).__init__(**kwargs)
        # stores tasks in queue regarding the github crawling
        self._crawl = queue.Queue()
        # indicates whether to keep running
        self.keep_running = False
        # self.console = Console(force_terminal=False)
        self.console = Console()

    @property
    def crawl(self) -> queue.Queue:
        """Get crawl task queue."""
        return self._crawl

    @override
    @abstractmethod
    def ask_all(self) -> Self:
        """Queue all tasks to be performed on the cloned repository."""
        # To be implemented in subclasses
        # This method should define the tasks to be performed on the cloned repository.
        pass

    @abstractmethod
    def execute(self) -> dict:
        """Execute the queued tasks via crawling the Github website. Handles rate limits if necessary.
        Returns:
          dict: The data retrieved by the executed tasks.
        Raises:
          urllib.error.HTTPError: If an HTTP error occurs during the request.
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
        """Execute the queued tasks via crawling the Github website.

        Returns:
          dict: The data retrieved by the executed tasks.
        """
        # Stores the merged data from all tasks
        res = {}
        # Stores the results of the tasks
        rest_res = []
        self.console.log(f"{self.__LOG_PREFIX} Starting with website crawling tasks")
        try:
            while item := self.crawl.get():
                self.console.log(f"{self.__LOG_PREFIX} Executing {item.__qualname__}")
                # Execute the task and append the result to rest_res
                rest_res.append(item())
                # Mark the task as done
                self.crawl.task_done()
                self.console.log(f"{self.__LOG_PREFIX} Finished {item.__qualname__}")
                # Check if the queue is empty and if we should stop running
                if not self.keep_running and self.crawl.empty():
                    break
        except queue.ShutDown:  # type: ignore[attr-defined]
            # Handle shutdown of the queue
            pass
        # Merge the results from all tasks into a single dictionary
        for elem in rest_res:
            res.update(elem)
        self.console.log(f"{self.__LOG_PREFIX} Finished website crawling tasks")
        return res
