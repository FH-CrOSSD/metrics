from crossd_metrics import ds, client
from gql.dsl import dsl_gql, DSLQuery, DSLInlineFragment
from graphql import GraphQLError
from typing import TypeVar
from crossd_metrics.Request import Request
import bs4
import urllib
from urllib.parse import quote

_Self = TypeVar('_Self', bound='Repository')


class Repository(Request):
    """docstring for Repository."""
    _RATELIMIT_QUERY = ds.Query.rateLimit.select(
        ds.RateLimit.cost, ds.RateLimit.limit, ds.RateLimit.remaining,
        ds.RateLimit.resetAt, ds.RateLimit.nodeCount, ds.RateLimit.used)

    def __init__(self, owner: str, name: str):
        super(Repository, self).__init__()
        self.owner = owner
        self.name = name
        self._reset_query()
        self.crawl = []
        self.rest = []
        self.post_graphql = []

    def _reset_query(self) -> None:
        self.query = ds.Query.repository(owner=self.owner, name=self.name)

    def ask_all(self) -> _Self:
        self.ask_dependencies().ask_funding_links().ask_security_policy(
        ).ask_contributing().ask_feature_requests(
        ).ask_closed_feature_requests().ask_dependents().ask_pull_requests()
        return self

    def ask_funding_links(self) -> _Self:
        self.query.select(
            ds.Repository.fundingLinks.select(ds.FundingLink.platform,
                                              ds.FundingLink.url))
        return self

    def ask_security_policy(self) -> _Self:
        self.query.select(ds.Repository.isSecurityPolicyEnabled)
        return self

    def ask_dependencies(self, after=None) -> _Self:
        self.query.select(
            ds.Repository.dependencyGraphManifests(
                first=10, after=after).select(
                    ds.DependencyGraphManifestConnection.edges.select(
                        ds.DependencyGraphManifestEdge.cursor,
                        ds.DependencyGraphManifestEdge.node.select(
                            ds.DependencyGraphManifest.filename,
                            ds.DependencyGraphManifest.dependenciesCount)),
                    ds.DependencyGraphManifestConnection.totalCount))
        self.post_graphql.append({
            'method':
            self.ask_dependencies,
            'key':
            lambda x: x['repository']['dependencyGraphManifests']
        })
        return self

        # dependencyGraphManifests{nodes{filename,dependencies{totalCount},dependenciesCount}}

    def ask_contributing(self) -> _Self:
        blob_fragment = DSLInlineFragment()
        blob_fragment.on(ds.Blob)
        blob_fragment.select(ds.Blob.oid, ds.Blob.byteSize)
        self.query.select(
            ds.Repository.object(expression="HEAD:CONTRIBUTING.md").select(
                blob_fragment).alias("contributing_md"),
            ds.Repository.object(expression="HEAD:CONTRIBUTING.txt").select(
                blob_fragment).alias("contributing_txt"),
            ds.Repository.object(expression="HEAD:CONTRIBUTING").select(
                blob_fragment).alias("contributing_raw"))
        return self

    def ask_feature_requests(self,
                             states=["CLOSED", "OPEN"],
                             alias="feature_requests") -> _Self:
        self.query.select(
            ds.Repository.issues(
                first=0,
                states=states,
                filterBy={
                    "labels": [
                        "enhancement", "feature", "feature request",
                        "feature-request"
                    ]
                }).select(ds.IssueConnection.totalCount).alias(alias))
        return self

    def ask_closed_feature_requests(self) -> _Self:
        return self.ask_feature_requests(states="CLOSED",
                                         alias="closed_feature_requests")

    def ask_dependents(self) -> _Self:
        self.crawl.append(self._get_dependents)
        return self

    def _get_dependents(self) -> dict:
        return {
            "dependents":
            int(
                bs4.BeautifulSoup(urllib.request.urlopen(
                    f"https://github.com/{quote(self.owner)}/{quote(self.name)}/network/dependents?dependent_type=REPOSITORY"
                ).read(),
                                  features="html5lib").
                find(
                    "a",
                    href=
                    f"/{quote(self.owner)}/{quote(self.name)}/network/dependents?dependent_type=REPOSITORY"
                ).get_text().strip().split(" ")[0].strip().replace(",", ""))
        }

    def ask_pull_requests(self, after=None) -> _Self:
        self.query.select(
            ds.Repository.pullRequests(
                first=100, states="MERGED", after=after).select(
                    ds.PullRequestConnection.totalCount,
                    ds.PullRequestConnection.edges.select(
                        ds.PullRequestEdge.cursor,
                        ds.PullRequestEdge.node.select(
                            ds.PullRequest.mergedAt,
                            ds.PullRequest.createdAt))))
        self.post_graphql.append({
            "method":
            self.ask_pull_requests,
            "key":
            lambda x: x['repository']['pullRequests']
        })
        return self

    def execute(self, rate_limit=False) -> dict:
        # execute first graphql query (paginations are done later), execute things to crawl from website and do rest api calls
        self.result = super().execute(rate_limit) | self._execute_crawl()
        count = 1

        # handle graphql queries that might require pagination
        while self.post_graphql:
            post_graphql = self.post_graphql
            self.post_graphql = []
            # reset query so that it can be used for pagination in cycles (e.g. page 1 of all things that paginate, then page 2 and so on)
            self._reset_query()
            for entry in post_graphql:
                # do not execute queries if pagination is not required (all results transmitted in initial query)
                if entry["key"](self.result)['totalCount'] > len(entry["key"](
                        self.result)['edges']):
                    entry["method"](
                        after=entry["key"](self.result)['edges'][-1]['cursor'])
            try:
                # execute pagination query
                tmp = super().execute(rate_limit)
            except GraphQLError:
                # Break if query is empty (local grapqhl error)
                break
            # merge new edges into results
            for elem in tmp['repository']:
                # update totalCount in case it changed
                self.result['repository'][elem]['totalCount'] = tmp[
                    'repository'][elem]['totalCount']
                # merge edges
                self.result['repository'][elem]['edges'].extend(
                    tmp['repository'][elem]['edges'])

            # merge rate limit stats (e.g. sum up costs)
            if rate_limit:
                self.result['rateLimit']['cost'] += tmp['rateLimit']['cost']
                self.result['rateLimit']['remaining'] = tmp['rateLimit'][
                    'remaining']
                self.result['rateLimit']['resetAt'] = tmp['rateLimit'][
                    'resetAt']
                self.result['rateLimit']['nodeCount'] += tmp['rateLimit'][
                    'nodeCount']
                self.result['rateLimit']['used'] = tmp['rateLimit']['used']

            # checks if something returned 0 elements and removes the followup query if necessary
            # this is needed, because Github returns a wrong totalCount for dependencyManifestGraphs
            # (e.g. tested with laurent22/Joplin which returned totalCount==81 whereas the real count was 80)
            for i, entry in enumerate(post_graphql):
                # tmp contained not elements
                if not len(entry["key"](tmp)['edges']) or entry["key"](
                        self.result)['totalCount'] <= len(entry["key"](
                            self.result)['edges']):
                    self.post_graphql.pop(i)

            print("page" + str(count))
            count += 1
        return self.result

    def _execute_crawl(self) -> dict:
        crawl_res = [elem() for elem in self.crawl]
        res = {}
        for elem in crawl_res:
            res.update(elem)
        return res