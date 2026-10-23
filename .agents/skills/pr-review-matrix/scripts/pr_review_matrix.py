#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["anyio>=4,<5", "trio>=0.25,<1", "httpx>=0.27,<1", "rich>=14,<15"]
# ///

"""Read GitHub review requests and render an authored-and-reviewing PR matrix."""

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from urllib.parse import urlsplit

import anyio
import httpx


class ReportError(Exception):
    """A complete, trustworthy report could not be produced."""


MAX_REQUESTS = 4


class GitHub:
    """Share a request limit across setup, repositories, and nested pagination."""

    def __init__(self, http, host="github.com"):
        self.http = http
        self.host = host
        self.limiter = anyio.CapacityLimiter(MAX_REQUESTS)

    async def json(self, method, path, **kwargs):
        """Reuse HTTP connections; one limit covers every request in the report."""
        if self.host == "github.com" or self.host.endswith(".ghe.com"):
            api = "api.github.com" if self.host == "github.com" else "api." + self.host
            url = f"https://{api}{path}"
        else:
            url = f"https://{self.host}/api" + (
                path if path == "/graphql" else "/v3" + path
            )
        try:
            async with self.limiter:
                with anyio.fail_after(90):
                    result = await self.http.request(method, url, **kwargs)
        except (httpx.HTTPError, TimeoutError) as error:
            raise ReportError(
                f"GitHub {method} {path}: {type(error).__name__}"
            ) from error
        if result.is_error:
            raise ReportError(f"GitHub {method} {path}: HTTP {result.status_code}")
        try:
            return result.json()
        except ValueError as error:
            raise ReportError("GitHub returned invalid JSON") from error

    async def repository(self, repo, fields):
        """Reject partial results rather than rendering missing data as blanks."""
        owner, name = repo.split("/")
        query = (
            "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){"
            + fields
            + "}}"
        )
        response = await self.json(
            "POST",
            "/graphql",
            json={"query": query, "variables": {"owner": owner, "name": name}},
        )
        if not isinstance(response, dict) or response.get("errors"):
            raise ReportError(f"{repo}: GitHub could not return complete GraphQL data")
        repository = (response.get("data") or {}).get("repository")
        if not isinstance(repository, dict):
            raise ReportError(f"{repo}: missing repository data")
        return repository


async def credentials(host):
    """Read one existing token into memory without logging or persisting its value."""
    names = (
        ("GH_TOKEN", "GITHUB_TOKEN")
        if host == "github.com" or host.endswith(".ghe.com")
        else ("GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")
    )
    token = next((os.environ[name] for name in names if os.environ.get(name)), None)
    if token:
        return token
    try:
        with anyio.fail_after(90):
            result = await anyio.run_process(
                ["gh", "auth", "token", "--hostname", host], check=False
            )
    except (OSError, TimeoutError) as error:
        raise ReportError(
            "Cannot read GitHub credentials; sign in with gh auth login"
        ) from error
    if result.returncode or not result.stdout.strip():
        raise ReportError("GitHub credentials unavailable; sign in with gh auth login")
    return result.stdout.decode().strip()


def repository_name(remote, host):
    """Resolve a Git remote or GH_REPO value without contacting a Git server."""
    if "://" in remote:
        url = urlsplit(remote)
        remote_host, path = url.hostname, url.path.lstrip("/")
    elif ":" in remote:
        address, path = remote.split(":", 1)
        remote_host = address.rsplit("@", 1)[-1]
    else:
        parts = remote.split("/")
        remote_host, path = (
            (parts[0], "/".join(parts[1:])) if len(parts) == 3 else (host, remote)
        )
    path = path.removesuffix(".git")
    if remote_host != host or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", path
    ):
        raise ReportError(
            "Cannot infer a repository on the selected GitHub host; supply --repo OWNER/REPO"
        )
    return path


async def current_repository(host):
    """Prefer GH_REPO, then gh's local default, then origin; no network operation."""
    if override := os.environ.get("GH_REPO"):
        return repository_name(override, host)
    try:
        with anyio.fail_after(90):
            default = await anyio.run_process(
                ["gh", "repo", "set-default", "--view"], check=False
            )
            if default.returncode:
                raise ReportError(
                    "Cannot read GitHub CLI's default repository; supply --repo OWNER/REPO"
                )
            if default.stdout.strip():
                return repository_name(default.stdout.decode().strip(), host)
            result = await anyio.run_process(
                ["git", "remote", "get-url", "origin"], check=False
            )
    except (OSError, TimeoutError) as error:
        raise ReportError(
            "Cannot discover the current repository; supply --repo OWNER/REPO"
        ) from error
    if result.returncode:
        raise ReportError(
            "Cannot discover the current repository; supply --repo OWNER/REPO"
        )
    return repository_name(result.stdout.decode().strip(), host)


async def concurrent_results(*operations):
    """Run independent operations together, preserving input order and failing together."""
    results = [None] * len(operations)

    async def collect(index, operation):
        results[index] = await operation()

    async with anyio.create_task_group() as tasks:
        for index, operation in enumerate(operations):
            tasks.start_soon(collect, index, operation)
    return results


# Bound both the outer PR connection and overflow aliases to keep queries small.
PR_BATCH_SIZE = 50
CONNECTION_PAGE_SIZE = 100
PAGE_INFO = "pageInfo { hasNextPage endCursor }"
CONNECTION_FIELDS = {
    "reviews": "nodes { fullDatabaseId state submittedAt author { login __typename } }",
    "reviewRequests": (
        "nodes { requestedReviewer { __typename "
        "... on User { login } ... on Bot { login } ... on Mannequin { login } "
        "... on Team { slug organization { login } } } }"
    ),
}


def connection_page(value, context, previous_cursor=None):
    """Validate nodes and an advancing cursor for each independently paged connection."""
    if not isinstance(value, dict):
        raise ReportError(f"{context}: missing connection")
    nodes, page = value.get("nodes"), value.get("pageInfo")
    if (
        not isinstance(nodes, list)
        or any(not isinstance(node, dict) for node in nodes)
        or not isinstance(page, dict)
        or type(page.get("hasNextPage")) is not bool
    ):
        raise ReportError(f"{context}: incomplete connection data")
    cursor = page.get("endCursor") if page["hasNextPage"] else None
    if page["hasNextPage"] and (
        not isinstance(cursor, str) or not cursor or cursor == previous_cursor
    ):
        raise ReportError(f"{context}: missing or non-advancing pagination cursor")
    return nodes, cursor


def connection_query(name, cursor=None):
    """Request only the fields needed to reconstruct review state."""
    after = ",after:" + json.dumps(cursor) if cursor is not None else ""
    return (
        f"{name}(first:{CONNECTION_PAGE_SIZE}{after})"
        + "{"
        + CONNECTION_FIELDS[name]
        + " "
        + PAGE_INFO
        + "}"
    )


async def complete_review_pages(github, repo, prs):
    """Batch overflow review and request pages, retaining separate cursors per PR."""
    pending = {}
    seen = {}
    for pr in prs:
        for name in CONNECTION_FIELDS:
            nodes, cursor = connection_page(
                pr.get(name), f"{repo}#{pr['number']} {name}"
            )
            pr[name] = nodes
            if cursor:
                key = (pr["number"], name)
                pending[key] = (pr, cursor)
                seen[key] = {cursor}

    async def fetch_batch(batch):
        fields = {}
        for (_, name), (pr, cursor) in batch:
            fields.setdefault(pr["number"], []).append(connection_query(name, cursor))
        repository = await github.repository(
            repo,
            " ".join(
                f"p{number}:pullRequest(number:{number}){{{' '.join(parts)}}}"
                for number, parts in fields.items()
            ),
        )
        return batch, repository

    while pending:
        entries = list(pending.items())
        batches = await concurrent_results(
            *(
                partial(fetch_batch, entries[start : start + PR_BATCH_SIZE])
                for start in range(0, len(entries), PR_BATCH_SIZE)
            )
        )
        for batch, repository in batches:
            for key, (pr, previous_cursor) in batch:
                number, name = key
                node = repository.get(f"p{number}")
                if not isinstance(node, dict):
                    raise ReportError(
                        f"{repo}#{number}: missing PR while paging {name}"
                    )
                nodes, cursor = connection_page(
                    node.get(name), f"{repo}#{number} {name}", previous_cursor
                )
                pr[name].extend(nodes)
                del pending[key]
                if cursor:
                    if cursor in seen[key]:
                        raise ReportError(
                            f"{repo}#{number} {name}: repeated pagination cursor"
                        )
                    seen[key].add(cursor)
                    pending[key] = (pr, cursor)


def graphql_actor(actor):
    """Normalize API transport fields without changing canonical reviewer identities."""
    if not isinstance(actor, dict) or actor.get("__typename") not in (
        "User",
        "Bot",
        "Mannequin",
    ):
        raise ReportError("A reviewer identity is unavailable or unsupported")
    login = actor.get("login")
    # GraphQL bot logins omit the suffix used by REST and saved nickname keys.
    if actor["__typename"] == "Bot" and login and not login.endswith("[bot]"):
        login += "[bot]"
    return {"login": login, "type": actor["__typename"]}


def resolve_graphql_pr(repo, node, exclude_bots=False):
    """Adapt complete GraphQL histories to the existing review-state rules."""
    requests, teams = [], []
    for request in node["reviewRequests"]:
        actor = request.get("requestedReviewer")
        if isinstance(actor, dict) and actor.get("__typename") == "Team":
            organization = actor.get("organization")
            if (
                not actor.get("slug")
                or not isinstance(organization, dict)
                or (
                    organization.get("login", "").casefold()
                    != repo.split("/")[0].casefold()
                )
            ):
                raise ReportError(f"{repo}#{node['number']}: unavailable team identity")
            teams.append({"slug": actor["slug"]})
        else:
            requests.append(graphql_actor(actor))
    reviews = [
        {
            "id": int(review["fullDatabaseId"]),
            "state": review["state"],
            "submitted_at": review["submittedAt"],
            "user": graphql_actor(review["author"]),
        }
        for review in node["reviews"]
        if review["state"] != "PENDING"
    ]
    return resolve_pr(
        repo,
        {
            "number": node["number"],
            "title": node["title"],
            "html_url": node["url"],
            "user": graphql_actor(node["author"]),
            "draft": node["isDraft"],
            "requested_reviewers": requests,
            "requested_teams": teams,
        },
        reviews,
        exclude_bots,
    )


async def fetch_prs(github, repo, state, user, authored_only=False, exclude_bots=False):
    """Fetch fresh repository pages with review histories and merge status together."""
    # REST's closed scope includes merged PRs as well as unmerged closed PRs.
    states = {
        "open": "[OPEN]",
        "closed": "[CLOSED,MERGED]",
        "all": "[OPEN,CLOSED,MERGED]",
    }[state]

    async def fetch_page(cursor):
        after = ",after:" + json.dumps(cursor) if cursor is not None else ""
        fields = (
            f"pullRequests(first:{PR_BATCH_SIZE},states:{states},"
            f"orderBy:{{field:CREATED_AT,direction:DESC}}{after})"
            "{nodes { number title url author { login __typename } isDraft "
            "isInMergeQueue autoMergeRequest { enabledAt } mergeable "
            + " ".join(connection_query(name) for name in CONNECTION_FIELDS)
            + "} "
            + PAGE_INFO
            + "}"
        )
        return await github.repository(repo, fields)

    async def complete_page(nodes):
        if authored_only:
            nodes = [
                node
                for node in nodes
                if node.get("author")
                and graphql_actor(node["author"])["login"].casefold() == user
            ]
        await complete_review_pages(github, repo, nodes)
        completed = []
        for node in nodes:
            pr = resolve_graphql_pr(repo, node, exclude_bots)
            # Merge status is only needed for PRs participating in this report.
            if pr.author == user or any(
                identity.key == user and identity.kind != "team"
                for identity in pr.reviewers
            ):
                apply_merge_status(pr, node)
            completed.append(pr)
        return completed

    cursor = None
    seen = set()
    result = []
    repository = await fetch_page(cursor)
    while True:
        nodes, next_cursor = connection_page(
            repository.get("pullRequests"), repo, cursor
        )
        if next_cursor is None:
            result.extend(await complete_page(nodes))
            return result
        if next_cursor in seen:
            raise ReportError(f"{repo}: repeated PR pagination cursor")
        seen.add(next_cursor)
        # Keep just one outer page ahead while completing nested review chains.
        completed, repository = await concurrent_results(
            partial(complete_page, nodes), partial(fetch_page, next_cursor)
        )
        result.extend(completed)
        cursor = next_cursor


@dataclass(frozen=True)
class Reviewer:
    """Canonical identity; aliases only affect display."""

    key: str
    kind: str = "person"


@dataclass
class PullRequest:
    """The metadata and effective review state needed for one table row."""

    repo: str
    number: int
    title: str
    url: str
    author: str
    draft: bool = False
    queue: str = ""
    mergeable: str = "UNKNOWN"
    commented: set[Reviewer] = field(default_factory=set)
    requested: set[Reviewer] = field(default_factory=set)
    decisions: dict[Reviewer, str] = field(default_factory=dict)
    reviewers: set[Reviewer] = field(default_factory=set)


def reviewer(user):
    """Preserve bot identity and compare GitHub logins case-insensitively."""
    if not user or not user.get("login"):
        raise ReportError(
            "A reviewer identity is unavailable (possibly a deleted account)"
        )
    login = user["login"].lower()
    return Reviewer(
        login,
        "bot" if user.get("type") == "Bot" or login.endswith("[bot]") else "person",
    )


def resolve_pr(repo, raw, reviews, exclude_bots=False):
    """Pending requests override historical decisions; comments leave decisions intact."""
    pr = PullRequest(
        repo,
        raw["number"],
        raw["title"],
        raw["html_url"],
        raw["user"]["login"].lower(),
        draft=bool(raw.get("draft")),
    )
    for user in raw.get("requested_reviewers", []):
        identity = reviewer(user)
        if identity.key != pr.author and not (exclude_bots and identity.kind == "bot"):
            pr.requested.add(identity)
    for team in raw.get("requested_teams", []):
        pr.requested.add(
            Reviewer(f"{repo.split('/')[0].lower()}/{team['slug'].lower()}", "team")
        )
    pr.reviewers.update(pr.requested)

    for review in sorted(
        reviews, key=lambda value: (value.get("submitted_at") or "", value["id"])
    ):
        state = review["state"].upper()
        if state == "PENDING":
            continue
        if state not in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED", "COMMENTED"}:
            raise ReportError(f"PR #{pr.number}: unrecognized review state {state}")
        identity = reviewer(review.get("user"))
        if identity.key == pr.author or (exclude_bots and identity.kind == "bot"):
            continue
        pr.reviewers.add(identity)
        if state in {"APPROVED", "CHANGES_REQUESTED"}:
            pr.decisions[identity] = state
        elif state == "DISMISSED":
            pr.decisions.pop(identity, None)
        elif state == "COMMENTED":
            pr.commented.add(identity)
    return pr


def cell(pr, identity):
    """A request is outstanding even when an earlier review approved the PR."""
    if identity in pr.requested:
        return "🟠"
    return {"APPROVED": "💚", "CHANGES_REQUESTED": "🟥"}.get(
        pr.decisions.get(identity), "💬" if identity in pr.commented else ""
    )


def apply_merge_status(pr, status):
    """Require explicit queue and conflict data; queue membership wins over auto-merge."""
    if (
        not isinstance(status, dict)
        or type(status.get("isInMergeQueue")) is not bool
        or "autoMergeRequest" not in status
        or status.get("mergeable") not in ("MERGEABLE", "CONFLICTING", "UNKNOWN")
        or (
            status["autoMergeRequest"] is not None
            and not isinstance(status["autoMergeRequest"], dict)
        )
    ):
        raise ReportError(f"{pr.repo}#{pr.number}: incomplete merge-status data")
    pr.mergeable = status["mergeable"]
    pr.queue = (
        "🔶"
        if status["isInMergeQueue"]
        else "🟦"
        if status["autoMergeRequest"] is not None
        else ""
    )


def markdown(value):
    """Keep titles and aliases inside one literal Markdown table cell."""
    text = " ".join(str(value).splitlines())
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for symbol in ("\\", "|", "`", "*", "_", "[", "]"):
        text = text.replace(symbol, "\\" + symbol)
    return text


def render(prs, aliases, user):
    """Render dynamic reviewer columns, preserving empty rows and pending totals."""
    if not prs:
        return "No matching PRs."
    columns = sorted(
        {identity for pr in prs for identity in pr.reviewers},
        key=lambda identity: (
            {"person": 0, "bot": 1, "team": 2}[identity.kind],
            aliases.get(identity.key, identity.key).casefold(),
            identity.key,
        ),
    )
    labels = {identity: aliases.get(identity.key, identity.key) for identity in columns}
    label_counts = Counter(labels.values())
    for identity in columns:
        if label_counts[labels[identity]] > 1:
            labels[identity] = f"{labels[identity]} ({identity.key})"
    user = user.casefold()
    first_section = "Authoring" if any(pr.author == user for pr in prs) else "Reviewing"
    header = [
        "",
        first_section,
        *(markdown(labels[identity]) for identity in columns),
        "Q",
    ]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---", "---", ":---:", *([":---:"] * len(columns))]) + " |",
    ]
    multi_repo = len({pr.repo for pr in prs}) > 1
    previous_authored = None
    for pr in sorted(
        prs,
        key=lambda value: (value.author != user, value.repo.casefold(), -value.number),
    ):
        authored = pr.author == user
        if previous_authored is not None and authored != previous_authored:
            lines.append(
                "| "
                + " | ".join(
                    ["", "**Reviewing**", *(f"**{label}**" for label in header[2:])]
                )
                + " |"
            )
        previous_authored = authored
        label = f"{pr.repo}#{pr.number}" if multi_repo else f"#{pr.number}"
        row = [
            f"[{markdown(label)}]({pr.url})",
            ("⛔ " if pr.mergeable == "CONFLICTING" else "") + markdown(pr.title),
            *(cell(pr, identity) for identity in columns),
            pr.queue,
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines.append(
        "| "
        + " | ".join(
            [
                "",
                "**Pending requests**",
                *(
                    str(sum(identity in pr.requested for pr in prs))
                    for identity in columns
                ),
                "",
            ]
        )
        + " |"
    )
    lines.extend(
        [
            "",
            "⛔ Title prefix: confirmed merge conflict (unknown mergeability is not marked)",
            "",
            "Q: 🟦 Merge when ready enabled · 🔶 In merge queue · Blank: neither",
            "",
            "🟠 Requested · 🟥 Changes requested · 💚 Approved · 💬 Comment-only review · Blank: no current request or active decision",
        ]
    )
    used_aliases = [
        f"{markdown(labels[identity])} = {markdown(identity.key)}"
        for identity in columns
        if identity.key in aliases
    ]
    if used_aliases:
        lines.extend(["", "Nicknames: " + "; ".join(used_aliases) + "."])
    return "\n".join(lines)


def load_aliases(path):
    """Read user-editable labels while keeping API identities unchanged."""
    try:
        aliases = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ReportError(f"Cannot read reviewer aliases: {error}") from error
    if not isinstance(aliases, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) or not value.strip()
        for key, value in aliases.items()
    ):
        raise ReportError(
            "Reviewer aliases must be a JSON object mapping logins to nonempty labels"
        )
    return {key.lower(): value for key, value in aliases.items()}


async def build_report(args):
    """Discover scope and fetch independent repositories under a shared request limit."""
    aliases = load_aliases(args.aliases)
    host = os.environ.get("GH_HOST", "github.com").lower()
    if not re.fullmatch(r"[a-z0-9.-]+", host):
        raise ReportError("GH_HOST must be a GitHub hostname")
    async with httpx.AsyncClient(
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "pr-review-matrix",
        },
        timeout=90,
        limits=httpx.Limits(max_connections=MAX_REQUESTS),
    ) as http:
        github = GitHub(http, host)

        async def discover_repos():
            repos = args.repo or [await current_repository(host)]
            repos = list(dict.fromkeys(repos))
            if any(
                not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
                for repo in repos
            ):
                raise ReportError("Repository names must use OWNER/REPO format")
            return repos

        async def discover_user():
            token = await credentials(host)
            http.headers["Authorization"] = "Bearer " + token
            return (
                args.user
                if args.user and args.user != "@me"
                else (await github.json("GET", "/user"))["login"]
            ).casefold()

        repos, user = await concurrent_results(discover_repos, discover_user)
        batches = await concurrent_results(
            *(
                partial(
                    fetch_prs,
                    github,
                    repo,
                    args.state,
                    user,
                    args.authored_only,
                    args.exclude_bots,
                )
                for repo in repos
            )
        )
    candidates = [pr for batch in batches for pr in batch]
    # Requests and submitted reviews are both in reviewers; unsubmitted
    # drafts of reviews and self-comments do not add reviewer identities.
    involved = [
        pr
        for pr in candidates
        if pr.author == user
        or (
            not args.authored_only
            and any(
                identity.key == user and identity.kind != "team"
                for identity in pr.reviewers
            )
        )
    ]
    drafts = sum(pr.draft for pr in involved) if not args.include_drafts else 0
    prs = [pr for pr in involved if args.include_drafts or not pr.draft]
    observed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    participation = (
        "authored" if args.authored_only else "authored, review requested, or reviewed"
    )
    scope = f"{', '.join(repos)} · user: {user} · {participation} · {args.state} PRs · {drafts} drafts excluded · fetched {observed_at}"
    return markdown(scope) + "\n\n" + render(prs, aliases, user)


def failure_messages(error):
    """Expose useful errors even when sibling tasks fail inside nested task groups."""
    if isinstance(error, BaseExceptionGroup):
        return [
            message for child in error.exceptions for message in failure_messages(child)
        ]
    return [str(error)]


def main(argv=None):
    """Print only complete reports; expected task failures remain concise CLI errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        action="append",
        help="OWNER/REPO; repeat for multiple repositories (default: current repo)",
    )
    parser.add_argument(
        "--user",
        help="GitHub login whose authored and reviewing PRs to show (default: authenticated user)",
    )
    parser.add_argument(
        "--authored-only",
        action="store_true",
        help="Show only PRs authored by this user",
    )
    parser.add_argument("--state", choices=["open", "closed", "all"], default="open")
    parser.add_argument("--include-drafts", action="store_true")
    parser.add_argument("--exclude-bots", action="store_true")
    parser.add_argument(
        "--rich",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Render with Rich (default); --no-rich prints plain Markdown",
    )
    parser.add_argument(
        "--aliases",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "reviewer-aliases.json",
    )
    args = parser.parse_args(argv)
    status = 0
    try:
        report = anyio.run(build_report, args, backend="trio")
        if args.rich:
            # Keep the Markdown output path independent of terminal rendering.
            from rich.console import Console
            from rich.markdown import Markdown

            Console().print(Markdown(report, hyperlinks=True))
        else:
            print(report)
    except* (ReportError, KeyError, TypeError, ValueError) as errors:
        print(
            "Cannot produce review matrix: " + "; ".join(failure_messages(errors)),
            file=sys.stderr,
        )
        status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
