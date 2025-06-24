import datetime
import json
import threading
import typing
import urllib
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Literal, Self, override
from urllib.parse import quote

import bs4  # type: ignore[import]
import requests  # type: ignore[import]
from crossd_metrics import constants, utils
from crossd_metrics.CloneRequest import CloneRequest
from crossd_metrics.CrawlRequest import CrawlRequest
from crossd_metrics.GraphRequest import GraphRequest
from crossd_metrics.RestRequest import RestRequest
from crossd_metrics.utils import (
    AdvisoryOrder,
    IsoDate,
    IssueCommentOrder,
    IssueOrder,
    PullRequestOrder,
    ReleaseOrder,
    RepositoryOrder,
    get_past,
    get_security_advisories,
    handle_rate_limit,
    merge_dicts,
    simple_pagination,
)
from dateutil.relativedelta import relativedelta
from gql.dsl import DSLInlineFragment  # type: ignore[import]
from rich.console import Console
from github.GithubException import GithubException  # type: ignore[import]
import datetime


class Repository(GraphRequest, RestRequest, CrawlRequest, CloneRequest):
    """Retrieves information about a GitHub repository."""

    __LOG_PREFIX = "[dark_sea_green4 bold][Repository][/dark_sea_green4 bold]"

    def __init__(self, owner: str, name: str, clone_opts: dict = {}):
        """Initializes the Repository object.

        Args:
          owner: str: Github repository owner username
          name: str: Github repository name
        """
        # Github owner username
        self.owner = owner
        # Github repository name
        self.name = name
        # rich object for logging
        # self.console = Console(force_terminal=True)
        self.console = Console()
        # indicates whether to keep queue running
        # # retrieve data from the last 6 months
        # self.since = datetime.timedelta(days=6 * 30)
        # self.since = None
        super(Repository, self).__init__(owner=owner, name=name)
        self.clone_opts = clone_opts
        self.keep_running = True

    @override
    def _reset_query(self) -> None:
        """Resets the GraphQL query object."""
        self.query = self.ds.Query.repository(owner=self.owner, name=self.name)

    @override
    def ask_all(self) -> Self:
        """Convenience function to retrieve all repo data.

        Returns:
            Self: The current instance of the Repository class.
        """
        (
            self.ask_dependencies_sbom()
            # .ask_dependencies_crawl()
            # .ask_dependencies()
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
            .ask_license()
            .ask_dates()
            .ask_subscribers()
            .ask_community_profile()
            .ask_contributors()
            .ask_releases()
            # .ask_releases_crawl()
            .ask_security_advisories()
            .ask_issues()
            .ask_forks()
            # .ask_workflow_runs()
            # .ask_dependabot_alerts()
            .ask_commits_clone()
            # .ask_commits()
            # .ask_commit_files()
            # .ask_commit_details()
            .ask_branches()
        )
        return self

    def ask_identifiers(self) -> Self:
        """Queue graphql task to retrieve the repository identifiers owner, name and nameWithOwner.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(
            self.ds.Repository.name,
            self.ds.Repository.nameWithOwner,
            self.ds.Repository.owner.select(self.ds.RepositoryOwner.login),
        )
        return self

    def ask_funding_links(self) -> Self:
        """Queue graphql task to retrieve the repository funding links.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(
            self.ds.Repository.fundingLinks.select(
                self.ds.FundingLink.platform, self.ds.FundingLink.url
            )
        )
        return self

    def ask_license(self) -> Self:
        """Queue graphql task to retrieve the repository license information.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(self.ds.Repository.licenseInfo.select(self.ds.License.spdxId))
        return self

    def ask_dates(self) -> Self:
        """Queue graphql task to retrieve the repository dates (createdAt, updatedAt, archivedAt, pushedAt).

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(
            self.ds.Repository.createdAt,
            self.ds.Repository.updatedAt,
            self.ds.Repository.archivedAt,
            self.ds.Repository.pushedAt,
        )
        return self

    def ask_subscribers(self) -> Self:
        """Queue graphql graphql task to retrieve the repository subscribers count.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(
            self.ds.Repository.stargazerCount,
            self.ds.Repository.watchers(first=0).select(self.ds.UserConnection.totalCount),
        )
        return self

    def ask_security_policy(self) -> Self:
        """Queue graphql task to retrieve whether the repository security policy is enabled.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(self.ds.Repository.isSecurityPolicyEnabled)
        return self

    def ask_security_advisories(
        self, orderBy: AdvisoryOrder = AdvisoryOrder("DESC", "PUBLISHED")
    ) -> Self:
        """Queue rest api task to retrieve the repository security advisories.
        The security advisories are retrieved via the REST API, as the GraphQL API does not support

        Args:
          orderBy: Literal["created", "updated", "published"]: sort results by property (Default value = "published")

        Returns:
            Self: The current instance of the Repository class.
        """
        self.rest.put(lambda: self._get_security_advisories(orderBy))
        return self

    def _get_security_advisories(
        self,
        orderBy: AdvisoryOrder = AdvisoryOrder("DESC", "PUBLISHED"),
        since: relativedelta | None = None,
    ) -> dict:
        """Get security advisories for the repository per rest api.

        Args:
          orderBy: Literal["created", "updated", "published"]: sort results by property (Default value = "published")

        Returns:
            dict: Dictionary containing the security advisories.
        """
        res: dict = {"advisories": []}
        # use modified function as the original function does not support sorting
        for x in get_security_advisories(self.gh.get_repo(f"{self.owner}/{self.name}"), orderBy):
            # check if the advisory is older than the since date
            past = get_past(since)
            if not x._rawData[orderBy.field.lower() + "_at"]:
                # if the advisory has no published_at date, skip it
                continue
            if (
                since
                and past
                and datetime.datetime.fromisoformat(x._rawData[orderBy.field.lower() + "_at"])
                < past
            ):
                break
            res["advisories"].append(x._rawData)
        return res

    def ask_dependabot_alerts(self, after: typing.Optional[str] = None) -> Self:
        """Queue graphql task to retrieve the dependabot alerts for the repository.

        Args:
          after: typing.Optional[str]: Github cursor for pagination (Default value = None)

        Returns:
            Self: The current instance of the Repository class.
        """
        # it is apparently not possible to get the security advisories for a repo via graphql
        # you can only get vulnerabilityAlerts for a Repo, which are only Dependatbot Alerts
        # https://docs.github.com/en/graphql/reference/objects#repositoryvulnerabilityalert
        # and the securityAdvisories Query https://docs.github.com/en/graphql/reference/queries#securityadvisories
        # can not be filtered by repo
        self.query.select(
            self.ds.Repository.hasVulnerabilityAlertsEnabled,
            self.ds.Repository.vulnerabilityAlerts(first=100, after=after).select(
                self.ds.RepositoryVulnerabilityAlertConnection.pageInfo.select(
                    self.ds.PageInfo.hasNextPage, self.ds.PageInfo.endCursor
                ),
                self.ds.RepositoryVulnerabilityAlertConnection.nodes.select(
                    self.ds.RepositoryVulnerabilityAlert.securityAdvisory.select(
                        self.ds.SecurityAdvisory.ghsaId,
                        self.ds.SecurityAdvisory.withdrawnAt,
                        self.ds.SecurityAdvisory.publishedAt,
                        self.ds.SecurityAdvisory.severity,
                        self.ds.SecurityAdvisory.cwes(first=100).select(
                            self.ds.CWEConnection.nodes.select(self.ds.CWE.cweId)
                        ),
                        self.ds.SecurityAdvisory.cvssSeverities.select(
                            self.ds.CvssSeverities.cvssV3.select(
                                self.ds.CVSS.score, self.ds.CVSS.vectorString
                            ),
                            self.ds.CvssSeverities.cvssV4.select(
                                self.ds.CVSS.score, self.ds.CVSS.vectorString
                            ),
                        ),
                        self.ds.SecurityAdvisory.identifiers.select(
                            self.ds.SecurityAdvisoryIdentifier.type,
                            self.ds.SecurityAdvisoryIdentifier.value,
                        ),
                        self.ds.SecurityAdvisory.vulnerabilities(first=100).select(
                            self.ds.SecurityVulnerabilityConnection.nodes.select(
                                self.ds.SecurityVulnerability.firstPatchedVersion.select(
                                    self.ds.SecurityAdvisoryPackageVersion.identifier
                                )
                            )
                        ),
                    ),
                    self.ds.RepositoryVulnerabilityAlert.state,
                ),
            ),
        )

        # queue method that checks if pagination is necessary
        self.paginations.append(
            simple_pagination("vulnerabilityAlerts", self.ask_security_advisories)
        )

        return self

    def ask_dependencies_sbom(self) -> Self:
        """Queue rest api task to retrieve the dependencies count of the repository via the SBOM information.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.rest.put(self._get_dependencies_sbom)
        return self

    def ask_dependencies_crawl(self) -> Self:
        """Queue crawl task to retrieve the dependencies count of the repository via the GitHub website.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.crawl.put(self._get_dependencies_crawl)
        return self

    def _get_dependencies_crawl(self) -> dict:
        """Crawl and scrape the dependencies count of the repository from the GitHub website.

        Returns:
            dict: Dictionary containing the dependencies count.
        """
        res = 0
        # scrape html via BeautifulSoup
        soup = bs4.BeautifulSoup(
            urllib.request.urlopen(
                f"https://github.com/{self.owner}/{self.name}/network/dependencies"
            ),
            features="html5lib",
        )
        deps = None
        try:
            deps = (
                soup.find("div", class_="Box")
                .find("svg", class_="octicon-package")
                .parent.text.strip()
            )
            if "No dependencies found" not in deps:
                # if dependencies are found, get the number
                res = int(deps.split(" ")[0].replace(",", ""))
        except AttributeError:
            # e.g. if repo is empty return 0
            pass

        return {"dependencies": {"count": int(res)}}

    def contributors_available(self) -> bool:
        try:
            self.gh.get_repo(f"{self.owner}/{self.name}").get_contributors().totalCount
            return True
        except GithubException as ge:
            if ge.status == 403 and "list is too large" in ge.message:
                return False
            else:
                self.console.log(ge)
                raise ge

    def ask_contributors(self) -> Self:
        """Queue rest api task to retrieve the contributors of the repository.
        Not available via GraphQL API.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.rest.put(self._get_contributors)
        return self

    def _get_contributors(self) -> dict:
        """Retrieves the contributors of the repository via the REST API.

        Returns:
            dict: Dictionary containing the contributors.
        """
        res: dict = {"users": []}
        contributors = self.gh.get_repo(f"{self.owner}/{self.name}").get_contributors()
        for cont in contributors:
            res["users"].append({"login": cont.login, "contributions": cont.contributions})
        return {"contributors": res}

    def ask_community_profile(self) -> Self:
        """Queue rest api task to retrieve the community profile of the repository.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.rest.put(self._get_community_profile)
        return self

    def _get_community_profile(self) -> dict:
        """Retrieves the community profile of the repository via the REST API.

        Returns:
            dict: Dictionary containing the community profile.
        """
        try:
            # get community profile via REST API
            # uses PyGithub requestJson as API call was not implemented in the library yet
            status, headers, body = self.gh.requester.requestJson(
                "GET",
                f"/repos/{self.owner}/{self.name}/community/profile",
            )
        except requests.exceptions.RetryError as re:
            # if all retries fail, try to get the data via the crawl method
            if str(re.args[0].reason) == "too many 500 error responses":
                try:
                    return self._get_dependencies_crawl()
                except urllib.error.HTTPError as httpe:
                    # handle rate limit
                    if httpe.status in [403, 429]:
                        return handle_rate_limit(
                            httpe.headers["x-ratelimit-reset"],
                            self._get_dependencies_crawl,
                        )
                    else:
                        # raise the error if it is not a rate limit error
                        raise httpe

        if status != 200:
            self.console.log(f"{self.__LOG_PREFIX} unable to retrieve community profile")
            return {"community_profile": None}

        body = json.loads(body)

        return {"community_profile": body}

    def _get_dependencies_sbom(self) -> dict:
        """Retrieves the dependencies count of the repository via the SBOM information per REST API call.

        Returns:
            dict: Dictionary containing the dependencies count.
        """
        try:
            # get SBOM information via REST API
            # uses PyGithub requestJson as API call was not implemented in the library yet
            status, headers, body = self.gh.requester.requestJson(
                "GET",
                f"/repos/{self.owner}/{self.name}/dependency-graph/sbom",
            )
        except requests.exceptions.RetryError as re:
            if str(re.args[0].reason) == "too many 500 error responses":
                # if all retries fail, try to get the data via the crawl method
                try:
                    self.console.log(
                        f"{self.__LOG_PREFIX} Getting dependencies via sbom failed, trying to get them via crawl method"
                    )
                    return self._get_dependencies_crawl()
                except urllib.error.HTTPError as httpe:
                    # handle rate limit
                    if httpe.status in [403, 429]:
                        return handle_rate_limit(
                            httpe.headers["x-ratelimit-reset"],
                            self._get_dependencies_crawl,
                        )
                    else:
                        # raise the error if it is not a rate limit error
                        raise httpe

        # might result in status 500
        # {
        #     "message": "Failed to generate SBOM: Request timed out.",
        #     "documentation_url": "https://docs.github.com/rest/dependency-graph/sboms#export-a-software-bill-of-materials-sbom-for-a-repository",
        #     "status": "500",
        # }

        if status != 200:
            self.console.log(f"{self.__LOG_PREFIX} unable to retrieve sbom")
            return {"dependencies": {"count": None, "names": None}}

        sbom = json.loads(body)["sbom"]
        # get the dependencies from the SBOM
        deps = set(
            elem["relatedSpdxElement"]
            for elem in sbom["relationships"]
            if elem["relationshipType"] == "DEPENDS_ON"
        )

        return {"dependencies": {"count": len(deps), "names": list(deps)}}

    def ask_dependencies(self, after: typing.Optional[str] = None) -> Self:
        """Queue graphql task to retrieve the dependencies of the repository.

        Args:
          after: typing.Optional[str]: Github cursor for pagination (Default value = None)

        Returns:
            Self: The current instance of the Repository class.s
        """
        self.query.select(
            # Graphql queries for dependencyGraphManifests time out easily
            # so we paginatie with a limit of 5, to make request faster
            self.ds.Repository.dependencyGraphManifests(first=5, after=after).select(
                self.ds.DependencyGraphManifestConnection.pageInfo.select(
                    self.ds.PageInfo.hasNextPage, self.ds.PageInfo.endCursor
                ),
                self.ds.DependencyGraphManifestConnection.edges.select(
                    self.ds.DependencyGraphManifestEdge.cursor,
                    self.ds.DependencyGraphManifestEdge.node.select(
                        self.ds.DependencyGraphManifest.filename,
                        self.ds.DependencyGraphManifest.dependenciesCount,
                        # without requesting edges, github returns always a dependencyCount of 0
                        self.ds.DependencyGraphManifest.dependencies(first=0).select(
                            self.ds.DependencyGraphDependencyConnection.totalCount
                        ),
                    ),
                ),
                self.ds.DependencyGraphManifestConnection.totalCount,
            )
        )

        # queue method that checks if pagination is necessary
        self.paginations.append(
            simple_pagination("dependencyGraphManifests", self.ask_dependencies)
        )

        return self

    def __since_filter(
        self,
        selector: str | int | list[str | int],
        since: datetime.datetime | relativedelta | None,
    ) -> Callable:
        """Returns a function that checks if the data is newer than since.

        Args:
          selector: str | int | list[str | int]: data selector to get iso date string in the data dict
          since: datetime.datetime | datetime.timedelta | None: Include data newer than since (Default value = datetime.timedelta(days=30 * 6))
          If sinc is datetime.timedelta, the function will check if the data is newer than now - since.

        Returns:
            Callable: Function that checks if the data is newer than since
        """
        if type(since) == datetime.datetime:
            # if since is a datetime object, use it as is
            past = since
        elif type(since) == relativedelta:
            # if since is a timedelta object, use it to calculate the past date
            past = datetime.datetime.now(datetime.UTC) - since
        elif type(since) == type(None):
            # if since is None, return a function that always returns True
            # (i.e. no filter)
            return lambda x: True
        else:
            raise TypeError(
                "since not of type datetime.datetime, dateutil.relativedelta.relativedelta or None"
            )

        def func(data: dict) -> bool:
            """
            Returns True if the data is newer than since.

            Args:
              data: dict: data dict to check

            Returns:
                bool: True if the data is newer than since
            """
            if type(selector) == str:
                # if selector is a string, get the value from repository
                selection = data["repository"][selector]
            elif type(selector) == list:
                # if selector is a list, get the value from the data dict
                # by traversing the dict
                selection = data
                for elem in selector:
                    selection = selection[elem]
            return datetime.datetime.fromisoformat(selection) > past

        return func

    def ask_contributing(self) -> Self:
        """Checks possible contribution policy files.
        The function checks for the following files:
        - CONTRIBUTING.md
        - CONTRIBUTING.txt
        - CONTRIBUTING

        Returns:
            Self: The current instance of the Repository class.
        """
        blob_fragment = DSLInlineFragment()
        blob_fragment.on(self.ds.Blob)
        blob_fragment.select(self.ds.Blob.oid, self.ds.Blob.byteSize)
        self.query.select(
            self.ds.Repository.object(expression="HEAD:CONTRIBUTING.md")
            .select(blob_fragment)
            .alias("contributing_md"),
            self.ds.Repository.object(expression="HEAD:CONTRIBUTING.txt")
            .select(blob_fragment)
            .alias("contributing_txt"),
            self.ds.Repository.object(expression="HEAD:CONTRIBUTING")
            .select(blob_fragment)
            .alias("contributing_raw"),
        )
        return self

    def ask_feature_requests(
        self,
        states: list[Literal["CLOSED", "OPEN"]] = ["CLOSED", "OPEN"],
        alias: str = "feature_requests",
        orderBy: IssueOrder = IssueOrder("DESC", "CREATED_AT"),
    ) -> Self:
        """Queue graphql task to retrieve the feature requests of the repository.

        Args:
          states: list[Literal["CLOSED", "OPEN"]]: Lisst of issue states. (Default value = ["CLOSED")
          alias: str: Alias to use in resulting dict. (Default value = "feature_requests")
          orderBy: IssueOrder: How to order results. (Default value = IssueOrder("DESC"), "CREATED_AT"):

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(
            self.ds.Repository.issues(
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
                orderBy=asdict(orderBy),
            )
            .select(self.ds.IssueConnection.totalCount)
            .alias(alias)
        )
        return self

    def ask_closed_feature_requests(self) -> Self:
        """Queue graphql task to retrieve the closed feature requests of the repository.

        Returns:
            Self: The current instance of the Repository class.
        """
        return self.ask_feature_requests(states=["CLOSED"], alias="closed_feature_requests")

    def ask_dependents(self) -> Self:
        """Queue crawl task to retrieve the dependents of the repository.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.crawl.put(self._get_dependents)
        return self

    def ask_releases(
        self,
        after: typing.Optional[str] = None,
        orderBy: ReleaseOrder = ReleaseOrder("DESC", "CREATED_AT"),
        since: relativedelta | None = relativedelta(months=12),
    ) -> Self:
        """Queue graphql task to retrieve the releases of the repository.
        Warning: Github API provides a totalCount of 1000 at max (same when paginating nodes).

        Args:
          after: typing.Optional[str]: Github cursor for pagination. (Default value = None)

        Returns:
            Self: The current instance of the Repository class.
        """
        # raise DeprecationWarning(
        #     "Github API provides a totalCount of 1000 at max (same when paginating nodes)"
        # )
        # tested with
        # Repository(owner="vercel", name="next.js")
        # Repository(owner="vercel", name="vercel")
        self.query.select(
            self.ds.Repository.releases(first=100, after=after, orderBy=asdict(orderBy)).select(
                self.ds.ReleaseConnection.totalCount,
                self.ds.ReleaseConnection.pageInfo.select(
                    self.ds.PageInfo.hasNextPage, self.ds.PageInfo.endCursor
                ),
                self.ds.ReleaseConnection.edges.select(
                    self.ds.ReleaseEdge.cursor,
                    self.ds.ReleaseEdge.node.select(
                        self.ds.Release.createdAt,
                        self.ds.Release.publishedAt,
                        self.ds.Release.tagName,
                        self.ds.Release.name,
                    ),
                ),
            )
        )
        self.paginations.append(
            simple_pagination(
                "releases",
                self.ask_releases,
                filters=[
                    self.__since_filter(
                        ["repository", "releases", "edges", -1, "node", "createdAt"],
                        since=since,
                    )
                ],
            )
        )
        # # for pagination, method: this method, key: dict key in result (to update)
        # self.post_graphql.append(
        #     {
        #         "method": self.ask_releases,
        #         "key": lambda x: x["repository"]["releases"],
        #     }
        # )
        return self

    def ask_releases_crawl(self) -> Self:
        """Queue crawl task to retrieve the releases of the repository via the Github website.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.crawl.put(self._get_release_count)
        return self

    def _get_release_count(self) -> dict:
        """Retrieves the release count of the repository via the Github website.

        Returns:
            dict: Dictionary containing the release count.
        """
        response = urllib.request.urlopen(
            f"https://github.com/{quote(self.owner)}/{quote(self.name)}"
        )
        # get owner and name from the result url (github may redirect e.g. if owner name changed)
        # for finding the correct a tag, we need the current owner and name
        owner, name = urllib.parse.urlparse(response.geturl()).path.split("/")[1:3]
        release_count = 0
        try:
            # get the number of releases from the webpage
            release_count = int(
                bs4.BeautifulSoup(
                    response.read(),
                    features="html5lib",
                )
                .find("a", href=f"/{quote(owner)}/{quote(name)}/releases")
                .find("span", class_="Counter")
                .text.replace(",", "")
                .strip()
            )
        except AttributeError:
            self.console.log(f"{self.__LOG_PREFIX} did not find release count")
            pass
        return {"releases": release_count}

    def ask_issue_comments(
        self,
        number: str | int,
        after: typing.Optional[str] = None,
        orderBy: IssueCommentOrder = IssueCommentOrder("DESC", "UPDATED_AT"),
        since: relativedelta | None = relativedelta(months=3),
    ) -> Self:
        """Queue graphql task to retrieve the comments of an issue of the repository.

        Args:
          number: str | int: Issue number
          after: typing.Optional[str]: Github cursor for pagination (Default value = None)
          orderBy: IssueCommentOrder: Sort order for the issue comments (Default value = IssueCommentOrder("DESC"), "UPDATED_AT")

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(
            self.ds.Repository.issue(number=number)
            .alias(f"issue{number}")
            .select(
                self.ds.Issue.createdAt,
                self.ds.Issue.comments(first=100, after=after, orderBy=asdict(orderBy)).select(
                    self.ds.IssueCommentConnection.totalCount,
                    self.ds.IssueCommentConnection.pageInfo.select(
                        self.ds.PageInfo.hasNextPage, self.ds.PageInfo.endCursor
                    ),
                    self.ds.IssueCommentConnection.edges.select(
                        self.ds.IssueCommentEdge.cursor,
                        self.ds.IssueCommentEdge.node.select(
                            self.ds.IssueComment.id,
                            self.ds.IssueComment.createdAt,
                            self.ds.IssueComment.updatedAt,
                        ),
                    ),
                ),
            )
        )

        def pagination(data: dict) -> list[Callable] | Callable | None:
            """Provides a function that checks if pagination is necessary. Check if comments are older than since.

            Args:
              data: dict: repository data dict to check

            Returns:
                list[Callable] | Callable | None: List of functions that checks if pagination is necessary.
                None if no pagination is necessary.
            """
            if data["repository"][f"issue{number}"]["comments"]["pageInfo"]["hasNextPage"]:
                # check if the last comment is older than since
                if self.__since_filter(
                    ["repository", f"issue{number}", "comments", "edges", -1, "node", "updatedAt"],
                    since=since,
                )(data):
                    return [
                        # get next page of comments
                        lambda: self.ask_issue_comments(
                            number,
                            after=data["repository"][f"issue{number}"]["comments"]["pageInfo"][
                                "endCursor"
                            ],
                        )
                    ]
            return None

        # add pagination function to the list of paginations
        self.paginations.append(pagination)

        return self

    def ask_issues(
        self,
        after: typing.Optional[str] = None,
        orderBy: IssueOrder = IssueOrder("DESC", "UPDATED_AT"),
        since: relativedelta | None = relativedelta(months=6),
    ) -> Self:
        """Queue graphql task to retrieve the issues of the repository.
        Also queues a pagination function retrieving the comments of the issues.

        Args:
          after: typing.Optional[str]: Github cursor for pagination (Default value = None)
          orderBy: IssueOrder: Sort order of issues (Default value = IssueOrder("DESC"), "CREATED_AT")

        Returns:
            Self: The current instance of the Repository class.
        """
        # NOTE: Issues via Graphql only contain issues (REST API includes pull requests)
        self.query.select(
            self.ds.Repository.issues(first=100, after=after, orderBy=asdict(orderBy)).select(
                self.ds.IssueConnection.totalCount,
                self.ds.IssueConnection.pageInfo.select(
                    self.ds.PageInfo.hasNextPage, self.ds.PageInfo.endCursor
                ),
                self.ds.IssueConnection.edges.select(
                    self.ds.IssueEdge.cursor,
                    self.ds.IssueEdge.node.select(
                        self.ds.Issue.closedAt,
                        self.ds.Issue.updatedAt,
                        self.ds.Issue.createdAt,
                        self.ds.Issue.number,
                        self.ds.Issue.state,
                        # self.ds.Issue.closedByPullRequestsReferences(first=0).select(
                        #     self.ds.PullRequestConnection.totalCount
                        # ),
                    ),
                ),
            )
        )

        def pagination(data: dict) -> list[Callable] | None:
            """Returns pagination functions for the issues comments and issues.

            Args:
              data: dict: repository data dict to check

            Returns:
                list[Callable] | None: List of functions that checks if pagination is necessary.
                None if no pagination is necessary.
            """
            # stores the pagination functions
            res = []
            cutoff = 0
            # get the last issue cursor
            for i, elem in enumerate(data["repository"]["issues"]["edges"]):
                # if the cursor is the same as the after cursor, set cutoff to the index
                if elem["cursor"] == after:
                    cutoff = i + 1
                    break

            def _get_func(num) -> Callable:
                """Returns a function that retrieves the comments of an issue.
                The function is created in a closure to avoid the late binding problem.

                Args:
                  num:  int: Issue number

                Returns:
                    Callable: Function that queues the retrieval of the comments of the issue
                """
                # copy by value
                return lambda: self.ask_issue_comments(str(num))

            # get comment retrieval functions for the newly retrieved issues
            tmp = [
                _get_func(x["node"]["number"])
                for x in data["repository"]["issues"]["edges"][cutoff:]
            ]

            res.extend(tmp)

            # check if pagination of issues is necessary
            if data["repository"]["issues"]["pageInfo"]["hasNextPage"]:
                if self.__since_filter(
                    [
                        "repository",
                        "issues",
                        "edges",
                        -1,
                        "node",
                        (
                            utils.to_prop_camel(orderBy.field)
                            if orderBy.field in ("CREATED_AT", "UPDATED_AT")
                            else "updatedAt"
                        ),
                    ],
                    since=since,
                )(data):
                    res.append(
                        lambda: self.ask_issues(
                            after=data["repository"]["issues"]["pageInfo"]["endCursor"]
                        )
                    )
            return res

        # add pagination function to the list of paginations
        self.paginations.append(pagination)

        return self

    def _get_dependents(self) -> dict:
        """Retrieves the dependents count of the repository via the Github website.

        Returns:
            dict: Dictionary containing the dependents count.
        """
        response = urllib.request.urlopen(
            f"https://github.com/{quote(self.owner)}/{quote(self.name)}/network/dependents?dependent_type=REPOSITORY"
        )
        # get owner and name from the result url (github may redirect e.g. if owner name changed)
        # for finding the correct a tag, we need the current owner and name
        owner, name = urllib.parse.urlparse(response.geturl()).path.split("/")[1:3]
        # get the number of total dependents from webpage
        res = 0
        soup = bs4.BeautifulSoup(
            response.read(),
            features="html5lib",
        )
        try:
            # get the number of dependents from the webpage
            deps = (
                soup.find(
                    "a",
                    href=lambda href: href
                    and href.startswith(f"/{quote(owner)}/{quote(name)}/network/dependents")
                    and "dependent_type=REPOSITORY" in href,
                )
                .get_text()
                .strip()
                .split(" ")[0]
                .strip()
                .replace(",", "")
            )
            res = int(deps)
        except AttributeError:
            pass

        return {"dependents": {"count": res}}

    def ask_forks(
        self,
        after: typing.Optional[str] = None,
        orderBy: RepositoryOrder = RepositoryOrder("DESC", "CREATED_AT"),
        since: relativedelta | None = relativedelta(months=6),
    ) -> Self:
        """Queues a graphql task to retrieve the forks of the repository.

        Args:
          after: typing.Optional[str]: Github cursor for pagination (Default value = None)
          orderBy: RepositoryOrder: Sort order (Default value = RepositoryOrder("DESC"), "CREATED_AT")

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(
            self.ds.Repository.forks(first=100, after=after, orderBy=asdict(orderBy)).select(
                self.ds.RepositoryConnection.pageInfo.select(
                    self.ds.PageInfo.hasNextPage, self.ds.PageInfo.endCursor
                ),
                self.ds.RepositoryConnection.nodes.select(
                    self.ds.Repository.created_at,
                    self.ds.Repository.id,
                    self.ds.Repository.updated_at,
                ),
            )
        )

        # queue method that checks if pagination is necessary
        # limit to pull requests that are newer than since
        self.paginations.append(
            simple_pagination(
                "forks",
                self.ask_forks,
                filters=[
                    self.__since_filter(
                        [
                            "repository",
                            "forks",
                            "nodes",
                            -1,
                            (
                                utils.to_prop_camel(orderBy.field)
                                if orderBy.field in ("CREATED_AT", "UPDATED_AT")
                                else "createdAt"
                            ),
                        ],
                        since=since,
                    )
                ],
            )
        )
        return self

    def ask_pull_comments(
        self,
        number: str | int,
        after: typing.Optional[str] = None,
        orderBy: IssueCommentOrder = IssueCommentOrder("DESC", "UPDATED_AT"),
        since: relativedelta | None = relativedelta(months=3),
    ) -> Self:
        """Queue graphql task to retrieve the comments of an issue of the repository.

        Args:
          number: str | int: Issue number
          after: typing.Optional[str]: Github cursor for pagination (Default value = None)
          orderBy: IssueCommentOrder: Sort order for the issue comments (Default value = IssueCommentOrder("DESC"), "UPDATED_AT")

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(
            self.ds.Repository.pullRequest(number=number)
            .alias(f"pull{number}")
            .select(
                self.ds.PullRequest.createdAt,
                self.ds.PullRequest.comments(
                    first=100, after=after, orderBy=asdict(orderBy)
                ).select(
                    self.ds.IssueCommentConnection.totalCount,
                    self.ds.IssueCommentConnection.pageInfo.select(
                        self.ds.PageInfo.hasNextPage, self.ds.PageInfo.endCursor
                    ),
                    self.ds.IssueCommentConnection.edges.select(
                        self.ds.IssueCommentEdge.cursor,
                        self.ds.IssueCommentEdge.node.select(
                            self.ds.IssueComment.id,
                            self.ds.IssueComment.createdAt,
                            self.ds.IssueComment.updatedAt,
                        ),
                    ),
                ),
            )
        )

        def pagination(data: dict) -> list[Callable] | Callable | None:
            """Provides a function that checks if pagination is necessary. Check if comments are older than since.

            Args:
              data: dict: repository data dict to check

            Returns:
                list[Callable] | Callable | None: List of functions that checks if pagination is necessary.
                None if no pagination is necessary.
            """
            if data["repository"][f"pull{number}"]["comments"]["pageInfo"]["hasNextPage"]:
                # check if the last comment is older than since
                if self.__since_filter(
                    ["repository", f"pull{number}", "comments", "edges", -1, "node", "updatedAt"],
                    since=since,
                )(data):
                    return [
                        # get next page of comments
                        lambda: self.ask_pull_comments(
                            number,
                            after=data["repository"][f"pull{number}"]["comments"]["pageInfo"][
                                "endCursor"
                            ],
                        )
                    ]
            return None

        # add pagination function to the list of paginations
        self.paginations.append(pagination)

        return self

    def ask_pull_requests(
        self,
        after: typing.Optional[str] = None,
        orderBy: PullRequestOrder = PullRequestOrder("DESC", "UPDATED_AT"),
        since: relativedelta | None = relativedelta(months=6),
    ) -> Self:
        """Queue graphql task to retrieve the pull requests of the repository.

        Args:
          after: typing.Optional[str]: Github cursor for pagination (Default value = None)
          orderBy: PullRequestOrder: Sort order (Default value = PullRequestOrder("DESC"), "CREATED_AT")

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(
            self.ds.Repository.pullRequests(first=100, after=after, orderBy=asdict(orderBy)).select(
                self.ds.PullRequestConnection.totalCount,
                self.ds.PullRequestConnection.pageInfo.select(
                    self.ds.PageInfo.hasNextPage, self.ds.PageInfo.endCursor
                ),
                self.ds.PullRequestConnection.edges.select(
                    self.ds.PullRequestEdge.cursor,
                    self.ds.PullRequestEdge.node.select(
                        self.ds.PullRequest.number,
                        self.ds.PullRequest.mergedAt,
                        self.ds.PullRequest.createdAt,
                        self.ds.PullRequest.closedAt,
                        self.ds.PullRequest.state,
                        self.ds.PullRequest.updatedAt,
                    ),
                ),
            )
        )

        def pagination(data: dict) -> list[Callable] | None:
            """Returns pagination functions for the issues comments and issues.

            Args:
              data: dict: repository data dict to check

            Returns:
                list[Callable] | None: List of functions that checks if pagination is necessary.
                None if no pagination is necessary.
            """
            # stores the pagination functions
            res = []
            cutoff = 0
            # get the last issue cursor
            for i, elem in enumerate(data["repository"]["pullRequests"]["edges"]):
                # if the cursor is the same as the after cursor, set cutoff to the index
                if elem["cursor"] == after:
                    cutoff = i + 1
                    break

            def _get_func(num) -> Callable:
                """Returns a function that retrieves the comments of an issue.
                The function is created in a closure to avoid the late binding problem.

                Args:
                  num:  int: Issue number

                Returns:
                    Callable: Function that queues the retrieval of the comments of the issue
                """
                # copy by value
                return lambda: self.ask_pull_comments(str(num))

            # get comment retrieval functions for the newly retrieved issues
            tmp = [
                _get_func(x["node"]["number"])
                for x in data["repository"]["pullRequests"]["edges"][cutoff:]
            ]

            res.extend(tmp)

            # check if pagination of issues is necessary
            if data["repository"]["pullRequests"]["pageInfo"]["hasNextPage"]:
                if self.__since_filter(
                    [
                        "repository",
                        "pullRequests",
                        "edges",
                        -1,
                        "node",
                        (
                            utils.to_prop_camel(orderBy.field)
                            if orderBy.field in ("CREATED_AT", "UPDATED_AT")
                            else "updatedAt"
                        ),
                    ],
                    since=since,
                )(data):
                    res.append(
                        lambda: self.ask_pull_requests(
                            after=data["repository"]["pullRequests"]["pageInfo"]["endCursor"]
                        )
                    )
            return res

        # queue method that checks if pagination is necessary
        # limit to pull requests that are newer than since
        # self.paginations.append(
        #     simple_pagination(
        #         "pullRequests",
        #         self.ask_pull_requests,
        #         filters=[
        #             self.__since_filter(
        #                 [
        #                     "repository",
        #                     "pullRequests",
        #                     "edges",
        #                     -1,
        #                     "node",
        #                     (
        #                         utils.to_prop_camel(orderBy.field)
        #                         if orderBy.field in ("CREATED_AT", "UPDATED_AT")
        #                         else "updatedAt"
        #                     ),
        #                 ],
        #                 since=since,
        #             )
        #         ],
        #     )
        # )

        self.paginations.append(pagination)

        return self

    def ask_readme(self) -> Self:
        """Queue graphql task to retrieve the README file of the repository.

        Returns:
            Self: The current instance of the Repository class.
        """
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
        blob_fragment.on(self.ds.Blob)
        blob_fragment.select(self.ds.Blob.text)
        self.query.select(
            *(
                self.ds.Repository.object(expression=f"HEAD:{readme}")
                .select(blob_fragment)
                .alias(utils.get_readme_index(readme))
                for readme in constants.readmes
            )
        )
        return self

    def ask_workflow_runs(self) -> Self:
        """Queue rest api task to retrieve the workflow runs of the repository.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.rest.put(self._get_workflow_runs)
        return self

    def ask_workflows(self) -> Self:
        """Queue rest api task to retrieve the workflows of the repository.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.rest.put(self._get_workflows)
        return self

    def ask_description(self) -> Self:
        """Queue graphql task to retrieve the description of the repository.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(self.ds.Repository.description)
        return self

    def _get_workflows(self) -> dict:
        """Retrieves the workflows of the repository via the REST API.

        Returns:
            dict: Dictionary containing the workflows.
        """
        # get workflows via REST api (not available via graphql)
        wfs = self.gh.get_repo(f"{self.owner}/{self.name}").get_workflows()
        res = []
        # store previous pagination size value
        old_per_page = self.gh.per_page
        # set per_page to 5 to avoid timeouts
        self.gh.per_page = 5

        self.console.log(f"{self.__LOG_PREFIX} Retrieving status of {wfs.totalCount} workflows")
        for wf in wfs:
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
        # revert pagination size to original value
        self.gh.per_page = old_per_page
        self.console.log(f"{self.__LOG_PREFIX} Finished getting workflows")
        return {"workflows": res}

    def _get_workflow_runs(self) -> dict:
        """Retrieves the workflow runs of the repository via the REST API.

        Returns:
            dict: Dictionary containing the workflow runs.
        """
        res = []
        count = 1
        # with self.console.status("Getting workflow runs..."):
        # runs = self.gh.get_repo(f"{self.owner}/{self.name}").get_workflow_runs(status="failure")

        self.console.log(f"{self.__LOG_PREFIX} Gettings workflow runs")
        runs = self.gh.get_repo(f"{self.owner}/{self.name}").get_workflow_runs()
        self.console.log(f"{self.__LOG_PREFIX} total runs: {runs.totalCount}")
        for wf in runs:
            res.append(
                {
                    "name": wf.name,
                    "conclusion": wf.conclusion,
                    "created_at": datetime.datetime.strftime(wf.created_at, "%Y-%m-%dT%H:%M:%S%z"),
                    "updated_at": datetime.datetime.strftime(wf.updated_at, "%Y-%m-%dT%H:%M:%S%z"),
                }
            )
            if count % 10 == 0:
                self.console.log(f"{self.__LOG_PREFIX} workflow {count}")
            count += 1
        return {"workflow_runs": res}

    def ask_commits_clone(
        self, since: datetime.datetime | relativedelta | None = relativedelta(months=12)
    ) -> Self:
        """Queue task that clones the git repository and retrieves the commits.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.clone.put(lambda: self._get_commits_clone(since))
        return self

    def _get_commits_clone(
        self, since: datetime.datetime | relativedelta | None = relativedelta(months=12)
    ) -> dict:
        """Retrieves the commits of the locally cloned repository.

        Returns:
            dict: Dictionary containing the commits.
        """
        res = []
        # get past date
        past = get_past(since)

        self.console.log(f"{self.__LOG_PREFIX} Gettings commits")
        # get commits from the local repository
        for i, commit in enumerate(self.repo.iter_commits(self.repo.active_branch.name)):
            if past and commit.committed_datetime < past:
                break
            # calculate the commit stats
            stat = commit.stats  # needs the previous commit to calculate the stats
            # check if the commit is older than the past date
            self.console.log(
                f"{commit.hexsha} {past} {commit.committed_datetime} {commit.committed_datetime < past}"
            )
            res.append(
                {
                    "sha": commit.hexsha,
                    "author": {"name": commit.author.name, "email": commit.author.email},
                    "committer": {
                        "name": commit.committer.name,
                        "email": commit.committer.email,
                    },
                    "authored_iso": commit.authored_datetime.isoformat(),
                    "committed_iso": commit.committed_datetime.isoformat(),
                    "message": commit.message,
                    "has_signature": bool(commit.gpgsig),
                    "insertions": stat.total["insertions"],
                    "deletions": stat.total["deletions"],
                    "co_authors": [{"name": x.name, "email": x.email} for x in commit.co_authors],
                    "files": list(stat.files.keys()),
                }
            )
            if i % 200 == 0:
                self.console.log(f"{self.__LOG_PREFIX} Currently at commit # {i}")
        self.console.log(f"{self.__LOG_PREFIX} Finished getting commits")
        return {"commits": res}

    def ask_commits(
        self,
        after: typing.Optional[str] = None,
        since: IsoDate | None = None,
        details: bool = True,
        diff: bool = True,
        # before: typing.Optional[str] = None,
    ) -> Self:
        """Queue graphql task to retrieve the commits of the repository.

        Args:
          after: typing.Optional[str]: Github cursor for pagination (Default value = None)
          since: IsoDate | None: Retrieve data newer than sice (Default value = None)

        Returns:
            Self: The current instance of the Repository class.
        """
        # if before and after:
        #     raise ValueError("before and after are mutually exclusive")
        # if before:
        #     raise NotImplementedError("before is currently not fully implemented")
        # index = 100
        # if before and (val := int(before.split(" ")[-1])) < 100:
        #     index = val

        self.query.select(
            self.ds.Repository.defaultBranchRef.select(
                self.ds.Ref.target.alias("last_commit").select(
                    DSLInlineFragment()
                    .on(self.ds.Commit)
                    .select(
                        self.ds.Commit.history(
                            # **{"first" if not before else "last": index},
                            first=100,
                            after=after,
                            since=since,
                            # before=before,
                        ).select(
                            self.ds.CommitHistoryConnection.pageInfo.select(
                                self.ds.PageInfo.hasNextPage,
                                self.ds.PageInfo.endCursor,
                                # self.ds.PageInfo.startCursor,
                                # self.ds.PageInfo.hasPreviousPage,
                            ),
                            self.ds.CommitHistoryConnection.edges.select(
                                self.ds.CommitEdge.cursor,
                                self.ds.CommitEdge.node.select(
                                    self.ds.Commit.authoredByCommitter,
                                    self.ds.Commit.oid,
                                    self.ds.Commit.authoredDate,
                                    self.ds.Commit.committedDate,
                                    self.ds.Commit.signature.select(
                                        self.ds.GitSignature.isValid,
                                        self.ds.GitSignature.verifiedAt,
                                        self.ds.GitSignature.state,
                                    ),
                                    self.ds.Commit.author.select(
                                        self.ds.GitActor.date,
                                        self.ds.GitActor.email,
                                        self.ds.GitActor.name,
                                        self.ds.GitActor.user.select(
                                            self.ds.User.login, self.ds.User.id
                                        ),
                                    ),
                                    self.ds.Commit.committer.select(
                                        self.ds.GitActor.date,
                                        self.ds.GitActor.email,
                                        self.ds.GitActor.name,
                                        self.ds.GitActor.user.select(
                                            self.ds.User.login, self.ds.User.id
                                        ),
                                    ),
                                    self.ds.Commit.additions if diff else self.ds.Commit.oid,
                                    self.ds.Commit.deletions if diff else self.ds.Commit.oid,
                                    self.ds.Commit.message,
                                    self.ds.Commit.messageBody,
                                ),
                            ),
                        )
                    )
                )
            )
        )

        def pagination(data: dict) -> list[Callable] | None:
            """Returns a function that checks if pagination is necessary.
            Also queues rest api functions for retrieving the commit details.

            Args:
              data: dict: repository data dict to check.

            Returns:
                list[Callable] | None: List of functions that checks if pagination is necessary.
                None if no pagination is necessary.
            """
            res = []
            # if details and not before:
            if details:
                cutoff = 0
                # get the last commit cursor
                # get new items to retrieve commit details for
                for i, elem in enumerate(
                    data["repository"]["defaultBranchRef"]["last_commit"]["history"]["edges"]
                ):
                    # if the cursor is the same as the after cursor, set cutoff to the index
                    if elem["cursor"] == after:
                        cutoff = i + 1
                        break

                def _get_func(num: int) -> Callable:
                    """Returns a function that retrieves the commit details.
                    The function is created in a closure to avoid the late binding problem.

                    Args:
                    num: int: Commit number

                    Returns:
                        Callable: Function that queues the retrieval of the commit details
                    """
                    # copy by value
                    return lambda: self._get_commit_details(str(num))

                # get commit retrieval functions for the newly retrieved commits
                tmp = [
                    _get_func(x["node"]["oid"])
                    for x in data["repository"]["defaultBranchRef"]["last_commit"]["history"][
                        "edges"
                    ][cutoff:]
                ]

                # queue the commit details rest api retrieval functions
                for elem in tmp:
                    self.rest.put(elem)

            # check if pagination of commits is necessary
            # if data["repository"]["defaultBranchRef"]["last_commit"]["history"]["pageInfo"][
            #     "hasNextPage" if after else "hasPreviousPage"
            # ]:
            if data["repository"]["defaultBranchRef"]["last_commit"]["history"]["pageInfo"][
                "hasNextPage"
            ]:
                # if not before:
                res.append(
                    lambda: self.ask_commits(
                        after=data["repository"]["defaultBranchRef"]["last_commit"]["history"][
                            "pageInfo"
                        ]["endCursor"],
                        details=details,
                        diff=diff,
                    )
                )
                # else:
                #     res.append(
                #         lambda: self.ask_commits(
                #             before=data["repository"]["defaultBranchRef"]["last_commit"]["history"][
                #                 "pageInfo"
                #             ]["startCursor"],
                #             details=details,
                #             diff=diff,
                #         )
                #     )
            return res

        # add pagination function to the list of paginations
        self.paginations.append(pagination)

        return self

    def ask_commits_count(self, since: IsoDate | None = None) -> Self:
        """Queue graphql task to retrieve the commits of the repository.

        Args:
          after: typing.Optional[str]: Github cursor for pagination (Default value = None)
          since: IsoDate | None: Retrieve data newer than sice (Default value = None)

        Returns:
            Self: The current instance of the Repository class.
        """
        # (datetime.date.today()-datetime.timedelta(days=30*6)).isoformat()
        self.query.select(
            self.ds.Repository.defaultBranchRef.select(
                self.ds.Ref.target.alias("last_commit").select(
                    DSLInlineFragment()
                    .on(self.ds.Commit)
                    .select(
                        self.ds.Commit.history(first=0, since=since).select(
                            self.ds.CommitHistoryConnection.totalCount
                        )
                    )
                )
            )
        )

        return self

    def ask_commit_files(self) -> Self:
        """Queue task that retrieves the commit files of the repository from the local clone.

        Returns:
            Self: The current instance of the Repository class.
        """
        self.clone.put(self._get_commit_files)
        return self

    def _get_commit_files(self) -> dict:
        """Retrieves list of files for each commit from the local clone.

        Returns:
            dict: Dictionary containing the commit files.
        """
        files = {
            commit.hexsha: list(commit.stats.files.keys())
            for commit in self.repo.iter_commits(self.repo.active_branch.name)
        }
        return {"commits": {"files": files}}

    def ask_commit_details(self, sha: str) -> Self:
        """Qeues a rest api task to retrieve the commit details of the repository.
        The commit details are not available via the GraphQL API.

        Args:
          sha: str: Commit sha

        Returns:
            Self: The current instance of the Repository class.
        """
        # as we need to make a request for every commit anyway, we could collect the commit data using this request instead of in the graphql query
        # that would save some nodes
        self.rest.put(lambda: self._get_commit_details(sha))
        return self

    def _get_commit_details(self, sha: str) -> dict:
        """Retrieves the commit details of the repository via the REST API.
        The commit details are not available via the GraphQL API.
        Returns the files per commit.

        Args:
          sha: str: Commit sha

        Returns:
            dict: Dictionary containing the commit details.
        """
        data = self.gh.get_repo(f"{self.owner}/{self.name}").get_commit(sha)._rawData
        return {f"commit_{sha}": [x["filename"] for x in data["files"]]}

    def ask_branches(self, after: typing.Optional[str] = None) -> Self:
        """Queues graphql task to retrieve the branches of the repository.

        Args:
          after: typing.Optional[str]: Github cursor for pagination (Default value = None)

        Returns:
            Self: The current instance of the Repository class.
        """
        self.query.select(
            # get branches via refPrefix
            self.ds.Repository.refs(first=100, refPrefix="refs/heads/", after=after)
            .alias("branches")
            .select(
                self.ds.RefConnection.totalCount,
                self.ds.RefConnection.pageInfo.select(
                    self.ds.PageInfo.hasNextPage, self.ds.PageInfo.endCursor
                ),
                self.ds.RefConnection.edges.select(
                    self.ds.RefEdge.cursor,
                    self.ds.RefEdge.node.alias("branch").select(
                        self.ds.Ref.name,
                        self.ds.Ref.target.alias("commit").select(
                            DSLInlineFragment()
                            .on(self.ds.Commit)
                            .select(
                                self.ds.Commit.author.select(self.ds.GitActor.date),
                                self.ds.Commit.committedDate,
                            )
                        ),
                        self.ds.Ref.associatedPullRequests(
                            first=100, orderBy=asdict(PullRequestOrder("DESC", "CREATED_AT"))
                        ).select(
                            self.ds.PullRequestConnection.nodes.select(self.ds.PullRequest.state)
                        ),
                    ),
                ),
            )
        )

        # queue method that checks if pagination is necessary
        self.paginations.append(simple_pagination("branches", self.ask_branches))
        return self

    @override
    def execute(self, rate_limit: bool = False, verbose: bool = False) -> dict:
        """Executes the queued tasks and retrieves the data from the repository.
        This method uses multithreading to execute the tasks in parallel.
        Each type of request (GraphQL, REST, Crawl, Clone) is executed in a separate thread.
        The results are merged into a single dictionary and returned.
        The method also handles pagination and rate limiting.

        Args:
          rate_limit: bool: whether to check rate limit (Default value = False)
          verbose: bool: verbose output (Default value = False)

        Returns:
            dict: Dictionary containing the results of the queries.
        """
        self.console.log(
            f"{self.__LOG_PREFIX} retrieving Data of repository {self.owner}/{self.name}"
        )

        with ThreadPoolExecutor(4) as tpe:
            # calls GraphRequest.execute
            graph = tpe.submit(super().execute, rate_limit)
            # calls RestRequest.execute (starts searching in MRO right of speicified type GraphRequest)
            rest = tpe.submit(super(GraphRequest, self).execute, rate_limit)
            # # calls CrawlRequest.execute(starts searching in MRO right of speicified type RestRequest)
            crawl = tpe.submit(super(RestRequest, self).execute)
            # # calls CloneRequest.execute(starts searching in MRO right of speicified type CrawlRequest)
            clone = tpe.submit(super(CrawlRequest, self).execute)
            # https://stackoverflow.com/questions/45704243/value-of-c-pytime-t-in-python
            # wait for all threads to finish
            try:
                # wait for graphql thread to finish
                gres = graph.result(timeout=threading.TIMEOUT_MAX)
                # close rest queue and wait for rest thread to finish
                self.rest.shutdown()  # type: ignore[attr-defined]
                rres = rest.result(timeout=threading.TIMEOUT_MAX)
                # close crawl queue and wait for crawl thread to finish
                self.crawl.shutdown()  # type: ignore[attr-defined]
                cres = crawl.result(timeout=threading.TIMEOUT_MAX)
                # close clone queue and wait for clone thread to finish
                self.clone.shutdown()  # type: ignore[attr-defined]
                cloneres = clone.result(timeout=threading.TIMEOUT_MAX)
            except Exception as e:
                print(e)
                # close queues on exception
                self.rest.shutdown()  # type: ignore[attr-defined]
                self.crawl.shutdown()  # type: ignore[attr-defined]
                self.clone.shutdown()  # type: ignore[attr-defined]
                # raise exception
                raise e

        self.console.log(f"{self.__LOG_PREFIX} Finished repository {self.owner}/{self.name}")
        # merge the results of the different threads
        return merge_dicts(gres, cres, rres, cloneres)
