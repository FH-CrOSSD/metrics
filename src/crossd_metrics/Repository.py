import datetime
import os.path
import time
import urllib
from typing import TypeVar
from urllib.parse import quote

import bs4
import github
import gql
import gql.transport
import gql.transport.exceptions
from crossd_metrics import constants, ds, gh, transport, utils
from crossd_metrics.Request import Request
from gql.dsl import DSLInlineFragment
from graphql import GraphQLError
from rich.progress import track

_Self = TypeVar("_Self", bound="Repository")
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console


class Repository(Request):
    """Class for retrieving information about a GitHub repository."""

    # for asking rate limit status
    _RATELIMIT_QUERY = ds.Query.rateLimit.select(
        ds.RateLimit.cost,
        ds.RateLimit.limit,
        ds.RateLimit.remaining,
        ds.RateLimit.resetAt,
        ds.RateLimit.nodeCount,
        ds.RateLimit.used,
    )

    def __init__(self, owner: str, name: str):
        super(Repository, self).__init__()
        self.owner = owner
        self.name = name
        self._reset_query()
        # stores tasks regarding the github website
        self.crawl = []
        # stores tasks regarding the github rest api
        self.rest = []
        # stores followup github graphql tasks (pagination)
        self.post_graphql = []
        self.console = Console(force_terminal=True)

    def _reset_query(self) -> None:
        self.query = ds.Query.repository(owner=self.owner, name=self.name)

    def ask_all(self) -> _Self:
        """Convenience function to retrieve all repo data."""
        (
            self.ask_dependencies()
            .ask_funding_links()
            .ask_security_policy()
            .ask_contributing()
            .ask_feature_requests()
            .ask_closed_feature_requests()
            .ask_dependents()
            .ask_pull_requests()
            .ask_readme()
            .ask_workflows()
            .ask_identifiers()
            .ask_description()
        )
        return self

    def ask_identifiers(self) -> _Self:
        self.query.select(
            ds.Repository.name,
            ds.Repository.nameWithOwner,
            ds.Repository.owner.select(ds.RepositoryOwner.login),
        )
        return self

    def ask_funding_links(self) -> _Self:
        self.query.select(
            ds.Repository.fundingLinks.select(
                ds.FundingLink.platform, ds.FundingLink.url
            )
        )
        return self

    def ask_security_policy(self) -> _Self:
        self.query.select(ds.Repository.isSecurityPolicyEnabled)
        return self

    def ask_dependencies(self, after=None) -> _Self:
        self.query.select(
            ds.Repository.dependencyGraphManifests(first=5, after=after).select(
                ds.DependencyGraphManifestConnection.edges.select(
                    ds.DependencyGraphManifestEdge.cursor,
                    ds.DependencyGraphManifestEdge.node.select(
                        ds.DependencyGraphManifest.filename,
                        ds.DependencyGraphManifest.dependenciesCount,
                        # without requesting edges, github returns always a dependencyCount of 0
                        ds.DependencyGraphManifest.dependencies(first=0).select(
                            ds.DependencyGraphDependencyConnection.totalCount
                        ),
                    ),
                ),
                ds.DependencyGraphManifestConnection.totalCount,
            )
        )
        # for pagination, method: this method, key: dict key in result (to update)
        self.post_graphql.append(
            {
                "method": self.ask_dependencies,
                "key": lambda x: x["repository"]["dependencyGraphManifests"],
            }
        )
        return self

        # dependencyGraphManifests{nodes{filename,dependencies{totalCount},dependenciesCount}}

    def ask_contributing(self) -> _Self:
        """Checks possible contribution policy files."""
        blob_fragment = DSLInlineFragment()
        blob_fragment.on(ds.Blob)
        blob_fragment.select(ds.Blob.oid, ds.Blob.byteSize)
        self.query.select(
            ds.Repository.object(expression="HEAD:CONTRIBUTING.md")
            .select(blob_fragment)
            .alias("contributing_md"),
            ds.Repository.object(expression="HEAD:CONTRIBUTING.txt")
            .select(blob_fragment)
            .alias("contributing_txt"),
            ds.Repository.object(expression="HEAD:CONTRIBUTING")
            .select(blob_fragment)
            .alias("contributing_raw"),
        )
        return self

    def ask_feature_requests(
        self, states=["CLOSED", "OPEN"], alias="feature_requests"
    ) -> _Self:
        self.query.select(
            ds.Repository.issues(
                first=0,
                states=states,
                filterBy={
                    "labels": [
                        "enhancement",
                        "feature",
                        "feature request",
                        "feature-request",
                    ]
                },
            )
            .select(ds.IssueConnection.totalCount)
            .alias(alias)
        )
        return self

    def ask_closed_feature_requests(self) -> _Self:
        return self.ask_feature_requests(
            states="CLOSED", alias="closed_feature_requests"
        )

    def ask_dependents(self) -> _Self:
        self.crawl.append(self._get_dependents)
        return self

    def _get_dependents(self) -> dict:
        response = urllib.request.urlopen(
            f"https://github.com/{quote(self.owner)}/{quote(self.name)}/network/dependents?dependent_type=REPOSITORY"
        )
        # get owner and name from the result url (github may redirect e.g. if owner name changed)
        # for finding the correct a tag, we need the current owner and name
        owner, name = urllib.parse.urlparse(response.geturl()).path.split("/")[1:3]
        # get the number of total dependents from webpage
        return {
            "dependents": int(
                bs4.BeautifulSoup(
                    response.read(),
                    features="html5lib",
                )
                .find(
                    "a",
                    href=lambda href: href
                    and href.startswith(
                        f"/{quote(owner)}/{quote(name)}/network/dependents"
                    )
                    and "dependent_type=REPOSITORY" in href,
                )
                .get_text()
                .strip()
                .split(" ")[0]
                .strip()
                .replace(",", "")
            )
        }

    def ask_pull_requests(self, after=None) -> _Self:
        self.query.select(
            ds.Repository.pullRequests(first=100, states="MERGED", after=after).select(
                ds.PullRequestConnection.totalCount,
                ds.PullRequestConnection.edges.select(
                    ds.PullRequestEdge.cursor,
                    ds.PullRequestEdge.node.select(
                        ds.PullRequest.mergedAt, ds.PullRequest.createdAt
                    ),
                ),
            )
        )
        # for pagination, method: this method, key: dict key in result (to update)
        self.post_graphql.append(
            {
                "method": self.ask_pull_requests,
                "key": lambda x: x["repository"]["pullRequests"],
            }
        )
        return self

    def ask_readme(self) -> _Self:
        # README file endings (not official)
        # https://github.com/joelparkerhenderson/github-special-files-and-paths#contributing
        # paths = [".github", "", "docs"]
        # endings = [".md", ".txt", ""]
        # readmes = [
        #     '/'.join(filter(None, (path, f"README{ending}"))) for path in paths
        #     for ending in endings
        # ]
        # rest api alternative - gives preferred README
        # https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28#get-a-repository-readme
        blob_fragment = DSLInlineFragment()
        blob_fragment.on(ds.Blob)
        blob_fragment.select(ds.Blob.text)
        self.query.select(
            *(
                ds.Repository.object(expression=f"HEAD:{readme}")
                .select(blob_fragment)
                .alias(utils.get_readme_index(readme))
                for readme in constants.readmes
            )
        )
        return self

    def ask_workflow_runs(self) -> _Self:
        self.rest.append(self._get_workflow_runs)
        return self

    def ask_workflows(self) -> _Self:
        self.rest.append(self._get_workflows)
        return self

    def ask_description(self) -> _Self:
        self.query.select(ds.Repository.description)
        return self

    def _get_workflows(self) -> dict:
        # get workflows via REST api (not available via graphql)
        wfs = gh.get_repo(f"{self.owner}/{self.name}").get_workflows()
        res = []
        old_per_page = gh.per_page
        gh.per_page = 5

        for wf in track(
            wfs, description="Retrieving status of workflows", total=wfs.totalCount
        ):
            for run in wf.get_runs():
                # only check finished workflow runs
                if run.conclusion:
                    res.append(
                        {
                            "name": wf.name,
                            "id": wf.id,
                            "path": wf.path,
                            "state": wf.state,
                            "created_at": datetime.datetime.strftime(
                                wf.created_at, "%Y-%m-%dT%H:%M:%S%z"
                            ),
                            "updated_at": datetime.datetime.strftime(
                                wf.updated_at, "%Y-%m-%dT%H:%M:%S%z"
                            ),
                            "last_run": {
                                "conclusion": run.conclusion,
                                "created_at": datetime.datetime.strftime(
                                    run.created_at, "%Y-%m-%dT%H:%M:%S%z"
                                ),
                                "updated_at": datetime.datetime.strftime(
                                    run.updated_at, "%Y-%m-%dT%H:%M:%S%z"
                                ),
                            },
                        }
                    )
                    break
        gh.per_page = old_per_page
        return {"workflows": res}

    def _get_workflow_runs(self) -> dict:
        res = []
        count = 1
        with self.console.status("Getting workflow runs..."):
            runs = gh.get_repo(f"{self.owner}/{self.name}").get_workflow_runs(
                status="failure"
            )
            self.console.log(f"total runs: {runs.totalCount}")
            for wf in runs:
                res.append(
                    {
                        "name": wf.name,
                        "conclusion": wf.conclusion,
                        "created_at": datetime.datetime.strftime(
                            wf.created_at, "%Y-%m-%dT%H:%M:%S%z"
                        ),
                        "updated_at": datetime.datetime.strftime(
                            wf.updated_at, "%Y-%m-%dT%H:%M:%S%z"
                        ),
                    }
                )
                if count % 10 == 0:
                    self.console.log(f"workflow {count}")
                count += 1
        return res

    def handle_rate_limit(self, timestamp, func):
        """Helper function for checking rate limit and sleeping for the specified time."""
        sleep_time = 60
        if timestamp:
            sleep_time = int(timestamp) - int(time.time())
        # add a little grace period
        sleep_time += 5
        self.console.log("rate limit exceeded - sleeping for " + str(sleep_time))
        time.sleep(sleep_time)
        # if rate limit is still exceed for whatever reason, crash and let the task queue retry later
        return func()

    def execute(self, rate_limit=False, verbose=False) -> dict:
        # execute first graphql query (paginations are done later), execute things to crawl from website and do rest api calls
        if verbose:
            self.console.log("retrieving Data")
        # ThreadPoolExecutor
        # do blocking requests in "parallel"
        # graphql page 1, crawling and rest api calls are executed in "parallel"
        tpe = ThreadPoolExecutor(3)
        graph = tpe.submit(super().execute, rate_limit)
        crawl = tpe.submit(self._execute_crawl)
        rest = tpe.submit(self._execute_rest)
        tpe.shutdown()

        # get graphql page 1 result from thread and check rate limit
        gres = {}
        try:
            gres = graph.result()
        except gql.transport.exceptions.TransportServerError as tse:
            if tse.code in [403, 429]:
                gres = self.handle_rate_limit(
                    transport.response_headers.get("x-ratelimit-reset"),
                    lambda: super().execute(rate_limit),
                )
            else:
                raise tse
        except gql.transport.exceptions.TransportQueryError as tqe:
            # handling this error is not necessary for the paginations as the connection uses a session
            # so if the Github loadbalancer assigns us to a host that can process our request
            # the paginations will also work as they are processed by the same host
            if (
                len(tqe.errors) == 1
                and tqe.errors[0]["path"] == ["repository", "dependencyGraphManifests"]
                and tqe.errors[0]["message"] == "timedout"
            ):
                for i in track(
                    range(20),
                    description="Retrying due to timedout dependencyGraphManifests",
                ):
                    try:
                        gres = super().execute(rate_limit)
                        break
                    except gql.transport.exceptions.TransportQueryError as tqe_inner:
                        if (
                            len(tqe_inner.errors) == 1
                            and tqe_inner.errors[0]["path"]
                            == ["repository", "dependencyGraphManifests"]
                            and tqe_inner.errors[0]["message"] == "timedout"
                        ):
                            # self.console.log("timedout dependencyGraphManifests")
                            pass
                        else:
                            raise tqe_inner
                else:
                    raise tqe
            else:
                raise tqe

        # get crawling webpage result from thread and check rate limit
        cres = {}
        try:
            cres = crawl.result()
        except urllib.error.HTTPError as httpe:
            if httpe.status in [403, 429]:
                cres = self.handle_rate_limit(
                    httpe.headers["x-ratelimit-reset"],
                    self._execute_crawl,
                )
            else:
                raise httpe

        # get rest api result from thread and check rate limit
        rres = {}
        try:
            rres = rest.result()
        except github.RateLimitExceededException as rlee:
            if rlee.status in [403, 429]:
                rres = self.handle_rate_limit(
                    rlee.headers["x-ratelimit-reset"],
                    self._execute_rest,
                )
            else:
                raise rlee

        # merge all results
        self.result = gres | cres | rres
        count = 1

        # handle graphql pagination
        with self.console.status("processing paginations ..."):
            # handle graphql queries that might require pagination
            while self.post_graphql:
                post_graphql = self.post_graphql
                self.post_graphql = []
                # reset query so that it can be used for pagination in cycles (e.g. page 1 of all things that paginate, then page 2 and so on)
                self._reset_query()
                for entry in post_graphql:
                    # do not execute queries if pagination is not required (all results transmitted in initial query)
                    # length > 0, because github gql returns totalCount: 1 when the list of edges is empty
                    if (
                        entry["key"](self.result)["totalCount"]
                        > (length := len(entry["key"](self.result)["edges"]))
                        and length > 0
                    ):
                        entry["method"](
                            after=entry["key"](self.result)["edges"][-1]["cursor"]
                        )
                try:
                    # execute pagination query
                    tmp = super().execute(rate_limit)
                except GraphQLError:
                    # Break if query is empty (local grapqhl error)
                    break
                except gql.transport.exceptions.TransportServerError as tse:
                    # sleep if graphql rate limit exceeded
                    if tse.code in [403, 429]:
                        gres = self.handle_rate_limit(
                            transport.response_headers.get("x-ratelimit-reset"),
                            lambda: super().execute(rate_limit),
                        )
                    else:
                        raise tse

                if not tmp:
                    # result of pagination empty
                    break

                # merge new edges into results
                for elem in tmp["repository"]:
                    # update totalCount in case it changed
                    self.result["repository"][elem]["totalCount"] = tmp["repository"][
                        elem
                    ]["totalCount"]
                    # merge edges
                    self.result["repository"][elem]["edges"].extend(
                        tmp["repository"][elem]["edges"]
                    )

                # merge rate limit stats (e.g. sum up costs)
                if rate_limit:
                    self.result["rateLimit"]["cost"] += tmp["rateLimit"]["cost"]
                    self.result["rateLimit"]["remaining"] = tmp["rateLimit"][
                        "remaining"
                    ]
                    self.result["rateLimit"]["resetAt"] = tmp["rateLimit"]["resetAt"]
                    self.result["rateLimit"]["nodeCount"] += tmp["rateLimit"][
                        "nodeCount"
                    ]
                    self.result["rateLimit"]["used"] = tmp["rateLimit"]["used"]

                # checks if something returned 0 elements and removes the followup query if necessary
                # this is needed, because Github returns a wrong totalCount for dependencyManifestGraphs
                # (e.g. tested with laurent22/Joplin which returned totalCount==81 whereas the real count was 80)
                for i, entry in enumerate(self.post_graphql):
                    # tmp contained not elements
                    if not len(entry["key"](tmp)["edges"]) or entry["key"](self.result)[
                        "totalCount"
                    ] <= len(entry["key"](self.result)["edges"]):
                        self.post_graphql.pop(i)

                if verbose:
                    self.console.log("page" + str(count))
                count += 1
        return self.result

    def _execute_crawl(self) -> dict:
        return self._execute_sequence(self.crawl)

    def _execute_rest(self) -> dict:
        return self._execute_sequence(self.rest)

    def _execute_sequence(self, seq) -> dict:
        rest_res = [elem() for elem in seq]
        res = {}
        for elem in rest_res:
            res.update(elem)
        return res
