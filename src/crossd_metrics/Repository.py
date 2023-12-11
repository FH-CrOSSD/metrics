import datetime
import os.path
import urllib
from typing import TypeVar
from urllib.parse import quote

import bs4
from gql.dsl import DSLInlineFragment
from graphql import GraphQLError
from rich.progress import track

from crossd_metrics import constants, ds, gh, utils
from crossd_metrics.Request import Request

_Self = TypeVar("_Self", bound="Repository")
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console

# from multiprocessing.pool import ThreadPool as Pool
# from multiprocessing import Pool


class Repository(Request):
    """docstring for Repository."""

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
        self.crawl = []
        self.rest = []
        self.post_graphql = []
        self.console = Console(force_terminal=True)

    def _reset_query(self) -> None:
        self.query = ds.Query.repository(owner=self.owner, name=self.name)

    def ask_all(self) -> _Self:
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
            ds.Repository.dependencyGraphManifests(first=10, after=after).select(
                ds.DependencyGraphManifestConnection.edges.select(
                    ds.DependencyGraphManifestEdge.cursor,
                    ds.DependencyGraphManifestEdge.node.select(
                        ds.DependencyGraphManifest.filename,
                        ds.DependencyGraphManifest.dependenciesCount,
                        ds.DependencyGraphManifest.dependencies(first=0).select(
                            ds.DependencyGraphDependencyConnection.totalCount
                        ),
                    ),
                ),
                ds.DependencyGraphManifestConnection.totalCount,
            )
        )
        self.post_graphql.append(
            {
                "method": self.ask_dependencies,
                "key": lambda x: x["repository"]["dependencyGraphManifests"],
            }
        )
        return self

        # dependencyGraphManifests{nodes{filename,dependencies{totalCount},dependenciesCount}}

    def ask_contributing(self) -> _Self:
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
        return {
            "dependents": int(
                bs4.BeautifulSoup(
                    urllib.request.urlopen(
                        f"https://github.com/{quote(self.owner)}/{quote(self.name)}/network/dependents?dependent_type=REPOSITORY"
                    ).read(),
                    features="html5lib",
                )
                .find(
                    "a",
                    href=f"/{quote(self.owner)}/{quote(self.name)}/network/dependents?dependent_type=REPOSITORY",
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

    def _get_workflows(self) -> dict:
        wfs = gh.get_repo(f"{self.owner}/{self.name}").get_workflows()
        res = []
        old_per_page = gh.per_page
        gh.per_page = 5

        for wf in track(
            wfs, description="Retrieving status of workflows", total=wfs.totalCount
        ):
            runs = wf.get_runs().reversed
            i = 0
            run = runs[i]
            # get last finished run (ignore currently running runs)
            while not run.conclusion:
                run = runs[i]
                i += 1
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
        gh.per_page = old_per_page
        # self.console.log(res)
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

        # return {
        #     "workflow_runs": [{
        #         "name":
        #         wf.name,
        #         "conclusion":
        #         wf.conclusion,
        #         "created_at":
        #         datetime.datetime.strftime(wf.created_at,
        #                                    "%Y-%m-%dT%H:%M:%S%z"),
        #         "updated_at":
        #         datetime.datetime.strftime(wf.updated_at,
        #                                    "%Y-%m-%dT%H:%M:%S%z")
        #     } for wf in gh.get_repo(
        #         f"{self.owner}/{self.name}").get_workflow_runs()]
        # }

    def execute(self, rate_limit=False, verbose=False) -> dict:
        # execute first graphql query (paginations are done later), execute things to crawl from website and do rest api calls
        if verbose:
            self.console.log("retrieving Data")
        # ThreadPoolExecutor
        # do blocking requests in "parallel"
        tpe = ThreadPoolExecutor(3)
        graph = tpe.submit(super().execute, rate_limit)
        crawl = tpe.submit(self._execute_crawl)
        rest = tpe.submit(self._execute_rest)
        tpe.shutdown()

        # multiprocess Pool or ThreadPool
        # p = Pool(3)
        # graph = p.apply_async(super().execute, [rate_limit])
        # crawl = p.apply_async(self._execute_crawl)
        # rest = p.apply_async(self._execute_rest)
        # p.close()
        # p.join()
        # self.result = (
        #     super().execute(rate_limit) | self._execute_crawl() | self._execute_rest()
        # )
        # self.result = graph.get() | crawl.get() | rest.get()
        self.result = graph.result() | crawl.result() | rest.result()
        count = 1

        with self.console.status("processing paginations ..."):
            # handle graphql queries that might require pagination
            while self.post_graphql:
                post_graphql = self.post_graphql
                self.post_graphql = []
                # reset query so that it can be used for pagination in cycles (e.g. page 1 of all things that paginate, then page 2 and so on)
                self._reset_query()
                for entry in post_graphql:
                    # do not execute queries if pagination is not required (all results transmitted in initial query)
                    if entry["key"](self.result)["totalCount"] > len(
                        entry["key"](self.result)["edges"]
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

                if not tmp:
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
                for i, entry in enumerate(post_graphql):
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
