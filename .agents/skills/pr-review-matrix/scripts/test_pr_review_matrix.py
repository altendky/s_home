#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["anyio>=4,<5", "trio>=0.25,<1", "httpx>=0.27,<1", "rich>=14,<15"]
# ///

"""Exercise review transitions, identity labels, pagination, and failed fetches."""

import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from functools import partial, wraps
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import patch

import anyio
import httpx
import pr_review_matrix as matrix


def trio_test(function):
    """Run async regression cases on the same backend as the CLI."""

    @wraps(function)
    def run(*args, **kwargs):
        async def timed():
            with anyio.fail_after(5):
                return await function(*args, **kwargs)

        return anyio.run(timed, backend="trio")

    return run


def fetch_prs(*args, **kwargs):
    async def run():
        return await matrix.fetch_prs(matrix.GitHub(None), *args, **kwargs)

    return anyio.run(run, backend="trio")


def complete_review_pages(*args):
    async def run():
        await matrix.complete_review_pages(matrix.GitHub(None), *args)

    return anyio.run(run, backend="trio")


def report_args(**overrides):
    values = {
        "repo": ["example/repo"],
        "user": "author",
        "state": "open",
        "authored_only": False,
        "exclude_bots": False,
        "include_drafts": False,
        "aliases": Path(__file__).resolve().parent.parent / "reviewer-aliases.json",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def raw_pr(requested=None):
    return {
        "number": 7,
        "title": "A | title [with] `markup`\nand lines",
        "html_url": "https://github.com/example/repo/pull/7",
        "user": {"login": "author"},
        "requested_reviewers": [{"login": login} for login in requested or []],
        "requested_teams": [],
    }


def review(review_id, state, login="j3m7"):
    return {
        "id": review_id,
        "state": state,
        "submitted_at": "2026-10-22T00:00:00Z",
        "user": {"login": login},
    }


def connection(nodes, cursor=None):
    """Model independently paginated GraphQL connections."""
    return {
        "nodes": nodes,
        "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor},
    }


def graphql_pr(number=7, author="author", reviews=None, requests=None):
    """Minimal API row containing all the matrix's requested fields."""
    return {
        "number": number,
        "title": f"PR {number}",
        "url": f"https://github.com/example/repo/pull/{number}",
        "author": {"login": author, "__typename": "User"},
        "isDraft": False,
        "reviews": connection(reviews or []),
        "reviewRequests": connection(requests or []),
        "mergeable": "MERGEABLE",
        "isInMergeQueue": False,
        "autoMergeRequest": None,
    }


def graphql_review(review_id, state, login="j3m7", kind="User"):
    """Review IDs can exceed GraphQL's 32-bit Int range."""
    return {
        "fullDatabaseId": str(review_id),
        "state": state,
        "submittedAt": "2026-10-22T00:00:00Z",
        "author": {"login": login, "__typename": kind},
    }


class ReviewMatrixTests(unittest.TestCase):
    def setUp(self):
        self.real_credentials = matrix.credentials
        self.credentials_patch = patch.object(
            matrix, "credentials", return_value="test-token"
        )
        self.credentials_patch.start()
        self.addCleanup(self.credentials_patch.stop)

    def test_comment_after_approval_preserves_approval(self):
        pr = matrix.resolve_pr(
            "example/repo", raw_pr(), [review(2, "COMMENTED"), review(1, "APPROVED")]
        )
        self.assertEqual(matrix.cell(pr, matrix.Reviewer("j3m7")), "💚")

    def test_rerequest_takes_precedence_over_earlier_approval(self):
        pr = matrix.resolve_pr(
            "example/repo", raw_pr(["j3m7"]), [review(1, "APPROVED")]
        )
        self.assertEqual(matrix.cell(pr, matrix.Reviewer("j3m7")), "🟠")

    def test_changes_then_dismissal_then_approval(self):
        history = [review(1, "APPROVED"), review(2, "CHANGES_REQUESTED")]
        for extra, expected in [
            (None, "🟥"),
            (review(3, "DISMISSED"), ""),
            (review(4, "APPROVED"), "💚"),
        ]:
            if extra:
                history.append(extra)
            pr = matrix.resolve_pr("example/repo", raw_pr(), history)
            self.assertEqual(matrix.cell(pr, matrix.Reviewer("j3m7")), expected)

    def test_nicknames_pending_totals_and_literal_titles(self):
        aliases = matrix.load_aliases(
            Path(__file__).resolve().parent.parent / "reviewer-aliases.json"
        )
        raw = raw_pr(["ericaltendorf", "j3m7", "secemp9"])
        raw["requested_teams"] = [{"slug": "platform"}]
        pr = matrix.resolve_pr(
            "example/repo",
            raw,
            [
                review(1, "APPROVED", "coderabbitai[bot]"),
                review(2, "COMMENTED", "author"),
            ],
        )
        table = matrix.render([pr], aliases, "author")
        self.assertIn("|  | Authoring | e | j | n | 🐇 | example/platform | Q |", table)
        self.assertIn("|  | **Pending requests** | 1 | 1 | 1 | 0 | 1 |  |", table)
        self.assertIn("| 🟠 | 🟠 | 🟠 | 💚 | 🟠 |", table)
        self.assertIn("A \\| title \\[with\\] \\`markup\\` and lines", table)
        self.assertNotIn(matrix.Reviewer("author"), pr.reviewers)

    def test_neutral_reviews_are_not_pending_or_approved(self):
        pr = matrix.resolve_pr(
            "example/repo",
            raw_pr(),
            [review(1, "COMMENTED"), review(2, "PENDING", "unsubmitted")],
        )
        self.assertEqual(matrix.cell(pr, matrix.Reviewer("j3m7")), "💬")
        self.assertNotIn(matrix.Reviewer("unsubmitted"), pr.reviewers)

    def test_pagination_and_failures_do_not_yield_partial_tables(self):
        with patch.object(
            matrix.GitHub, "json", side_effect=matrix.ReportError("API unavailable")
        ):
            output, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                status = matrix.main(["--repo", "example/repo", "--user", "author"])
            self.assertEqual(status, 1)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("API unavailable", errors.getvalue())

    def test_combined_scope_and_authored_only(self):
        def make(number, author="other", requested=None, draft=False):
            raw = raw_pr(requested)
            raw.update(
                number=number,
                title=f"scope-pr-{number}",
                html_url=f"https://github.com/example/repo/pull/{number}",
                user={"login": author},
                draft=draft,
            )
            return raw

        prs = [
            make(1, "altendky"),
            make(2, requested=["altendky"]),
            make(3),
            make(4),
            make(5, "altendky"),
            make(6, "altendky", draft=True),
            make(7),
            make(8, draft=True),
        ]
        histories = {
            3: [review(1, "COMMENTED", "altendky")],
            4: [review(1, "APPROVED", "j3m7")],
            5: [review(1, "COMMENTED", "altendky")],
            7: [review(1, "PENDING", "altendky")],
            8: [review(1, "APPROVED", "altendky")],
        }

        def fetch(github, repo, state, user, authored_only, exclude_bots):
            return [
                matrix.resolve_pr(
                    repo, raw, histories.get(raw["number"], []), exclude_bots
                )
                for raw in prs
                if not authored_only or raw["user"]["login"] == user
            ]

        for extra, expected, drafts in [
            ([], {1, 2, 3, 5}, 2),
            (["--authored-only"], {1, 5}, 1),
            (["--include-drafts"], {1, 2, 3, 5, 6, 8}, 0),
        ]:
            with (
                self.subTest(options=extra),
                patch.object(matrix, "fetch_prs", side_effect=fetch),
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    status = matrix.main(
                        [
                            "--repo",
                            "example/repo",
                            "--user",
                            "ALTENDKY",
                            "--no-rich",
                            *extra,
                        ]
                    )
                self.assertEqual(status, 0)
                report = output.getvalue()
                for number in range(1, 9):
                    self.assertEqual(
                        report.count(f"[#{number}]"), int(number in expected)
                    )
                self.assertIn(f"{drafts} drafts excluded", report)
                section_row = "|  | **Reviewing** | **k** | **Q** |"
                self.assertEqual(
                    report.splitlines().count(section_row),
                    int(not extra or extra == ["--include-drafts"]),
                )
                if not extra:
                    self.assertLess(report.index("[#5]"), report.index("[#1]"))
                    self.assertLess(report.index("[#1]"), report.index(section_row))
                    self.assertLess(report.index(section_row), report.index("[#3]"))
                    self.assertLess(report.index("[#3]"), report.index("[#2]"))
                if not extra:
                    self.assertIn("|  | Authoring | k | Q |", report)
                    self.assertIn("scope-pr-2 | 🟠 |  |", report)
                    self.assertIn("scope-pr-3 | 💬 |  |", report)
                    self.assertIn("k = altendky", report)

    def test_queue_states_and_queue_precedence(self):
        prs = []
        for number, queued, auto in [
            (7, False, None),
            (8, False, {"enabledAt": "now"}),
            (9, True, None),
            (10, True, {"enabledAt": "now"}),
        ]:
            raw = raw_pr()
            raw["number"] = number
            prs.append(matrix.resolve_pr("example/repo", raw, []))
            status = {
                "isInMergeQueue": queued,
                "autoMergeRequest": auto,
                "mergeable": "MERGEABLE",
            }
            matrix.apply_merge_status(prs[-1], status)
        self.assertEqual([pr.queue for pr in prs], ["", "🟦", "🔶", "🔶"])
        table = matrix.render(prs, {}, "author")
        self.assertIn("|  | Authoring | Q |", table)
        self.assertIn("| 🔶 |", table)
        self.assertIn("| 🟦 |", table)

    def test_missing_queue_data_is_not_treated_as_neither(self):
        pr = matrix.resolve_pr("example/repo", raw_pr(), [])
        for response in [{"autoMergeRequest": None}, None, {}]:
            with (
                self.subTest(response=response),
                self.assertRaises(matrix.ReportError),
            ):
                matrix.apply_merge_status(pr, response)

    def test_only_confirmed_conflicts_prefix_the_title(self):
        for state in ("CONFLICTING", "MERGEABLE", "UNKNOWN"):
            pr = matrix.resolve_pr("example/repo", raw_pr(), [])
            status = {
                "isInMergeQueue": False,
                "autoMergeRequest": {"enabledAt": "now"},
                "mergeable": state,
            }
            with self.subTest(state=state):
                matrix.apply_merge_status(pr, status)
                table = matrix.render([pr], {}, "author")
                title_cell = table.splitlines()[2].split(" | ")[1]
                self.assertEqual(title_cell.startswith("⛔ "), state == "CONFLICTING")
                self.assertEqual(pr.queue, "🟦")

    def test_missing_conflict_data_is_not_assumed_mergeable(self):
        pr = matrix.resolve_pr("example/repo", raw_pr(), [])
        status = {"isInMergeQueue": False, "autoMergeRequest": None}
        with self.assertRaises(matrix.ReportError):
            matrix.apply_merge_status(pr, status)

    def test_graphql_metadata_and_outer_pagination(self):
        responses = [
            {
                "data": {
                    "repository": {
                        "pullRequests": connection([graphql_pr(1)], "next-pr")
                    }
                }
            },
            {"data": {"repository": {"pullRequests": connection([graphql_pr(2)])}}},
        ]
        with patch.object(matrix.GitHub, "json", side_effect=responses) as api:
            prs = fetch_prs("example/repo", "open", "author")
        self.assertEqual([pr.number for pr in prs], [1, 2])
        self.assertEqual(api.call_count, 2)
        query = api.call_args_list[0].kwargs["json"]["query"]
        for field in (
            "reviews(first:",
            "reviewRequests(first:",
            "mergeable",
            "isInMergeQueue",
            "autoMergeRequest",
        ):
            self.assertIn(field, query)
        self.assertIn('after:"next-pr"', api.call_args_list[1].kwargs["json"]["query"])

    def test_nested_pagination_keeps_all_reviews_and_requests(self):
        first = graphql_pr(1)
        first["reviews"] = connection(
            [graphql_review(i, "COMMENTED", "commenter") for i in range(1, 100)]
            + [graphql_review(100, "APPROVED", "j3m7")],
            "r1",
        )
        first["reviewRequests"] = connection(
            [
                {"requestedReviewer": {"__typename": "User", "login": f"person{i}"}}
                for i in range(100)
            ],
            "q1",
        )
        second = graphql_pr(2, author="other")
        second["reviews"] = connection([], "r2")
        responses = [
            {"data": {"repository": {"pullRequests": connection([first, second])}}},
            {
                "data": {
                    "repository": {
                        "p1": {
                            "reviews": connection(
                                [graphql_review(101, "COMMENTED", "j3m7")], "r1-again"
                            ),
                            "reviewRequests": connection(
                                [
                                    {
                                        "requestedReviewer": {
                                            "__typename": "User",
                                            "login": "late-request",
                                        }
                                    }
                                ]
                            ),
                        },
                        "p2": {
                            "reviews": connection(
                                [graphql_review(2**40, "APPROVED", "author")]
                            )
                        },
                    }
                }
            },
            {
                "data": {
                    "repository": {
                        "p1": {
                            "reviews": connection(
                                [graphql_review(102, "CHANGES_REQUESTED", "j3m7")]
                            ),
                        }
                    }
                }
            },
        ]
        with patch.object(matrix.GitHub, "json", side_effect=responses) as api:
            prs = fetch_prs("example/repo", "open", "author")
        self.assertEqual(api.call_count, 3)
        self.assertEqual(len(prs[0].requested), 101)
        self.assertEqual(matrix.cell(prs[0], matrix.Reviewer("j3m7")), "🟥")
        self.assertEqual(matrix.cell(prs[1], matrix.Reviewer("author")), "💚")
        overflow = api.call_args_list[1].kwargs["json"]["query"]
        for cursor in ("r1", "q1", "r2"):
            self.assertIn(f'after:"{cursor}"', overflow)
        self.assertNotIn(
            "reviewRequests", api.call_args_list[2].kwargs["json"]["query"]
        )
        self.assertNotIn("p2:", api.call_args_list[2].kwargs["json"]["query"])

    def test_graphql_state_mapping_and_authored_only(self):
        for state, states in [
            ("open", "[OPEN]"),
            ("closed", "[CLOSED,MERGED]"),
            ("all", "[OPEN,CLOSED,MERGED]"),
        ]:
            unrelated = graphql_pr(2, "other")
            unrelated["reviews"] = None
            with (
                self.subTest(state=state),
                patch.object(
                    matrix.GitHub,
                    "json",
                    return_value={
                        "data": {
                            "repository": {
                                "pullRequests": connection([graphql_pr(1), unrelated])
                            }
                        }
                    },
                ) as api,
            ):
                prs = fetch_prs("example/repo", state, "author", authored_only=True)
                self.assertEqual([pr.number for pr in prs], [1])
                self.assertIn("states:" + states, api.call_args.kwargs["json"]["query"])

    def test_graphql_bots_teams_and_numeric_review_order(self):
        node = graphql_pr(
            reviews=[
                graphql_review(10, "COMMENTED", "robot", "Bot"),
                graphql_review(9, "APPROVED", "robot", "Bot"),
                graphql_review(11, "APPROVED", "j3m7"),
            ],
            requests=[
                {"requestedReviewer": {"__typename": "User", "login": "j3m7"}},
                {"requestedReviewer": {"__typename": "Bot", "login": "requested-bot"}},
                {
                    "requestedReviewer": {
                        "__typename": "Team",
                        "slug": "platform",
                        "organization": {"login": "example"},
                    }
                },
            ],
        )
        complete_review_pages("example/repo", [node])
        pr = matrix.resolve_graphql_pr("example/repo", node)
        self.assertEqual(matrix.cell(pr, matrix.Reviewer("robot[bot]", "bot")), "💚")
        self.assertIn(matrix.Reviewer("requested-bot[bot]", "bot"), pr.requested)
        self.assertEqual(matrix.cell(pr, matrix.Reviewer("j3m7")), "🟠")
        self.assertIn(matrix.Reviewer("example/platform", "team"), pr.requested)
        filtered = matrix.resolve_graphql_pr("example/repo", node, exclude_bots=True)
        self.assertFalse(any(r.kind == "bot" for r in filtered.reviewers))

    def test_late_graphql_failure_does_not_print_partial_table(self):
        first = graphql_pr(1, "author")
        first["reviews"] = connection([], "more")
        responses = [
            {"data": {"repository": {"pullRequests": connection([first])}}},
            {
                "data": {"repository": {"p1": {"reviews": connection([])}}},
                "errors": [{"message": "partial failure"}],
            },
        ]
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(matrix.GitHub, "json", side_effect=responses),
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            status = matrix.main(["--repo", "example/repo", "--user", "author"])
        self.assertEqual(status, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("complete GraphQL data", errors.getvalue())

    def test_invalid_connection_or_cursor_fails(self):
        for value in (
            None,
            {"nodes": [], "pageInfo": {}},
            connection([None]),
            connection([], "same"),
        ):
            with self.subTest(value=value), self.assertRaises(matrix.ReportError):
                matrix.connection_page(value, "context", "same")
        node = graphql_pr()
        node["reviews"] = connection([], "same")
        with (
            patch.object(
                matrix.GitHub,
                "json",
                return_value={
                    "data": {"repository": {"p7": {"reviews": connection([], "same")}}}
                },
            ),
            self.assertRaises(matrix.ReportError),
        ):
            complete_review_pages("example/repo", [node])

    def test_unknown_or_missing_requested_identity_fails(self):
        for actor in (
            None,
            {"__typename": "EnterpriseTeam"},
            {"__typename": "User"},
            {"__typename": "Team", "slug": "private"},
        ):
            node = graphql_pr(requests=[{"requestedReviewer": actor}])
            complete_review_pages("example/repo", [node])
            with self.subTest(actor=actor), self.assertRaises(matrix.ReportError):
                matrix.resolve_graphql_pr("example/repo", node)

    def test_imported_actors_and_unsubmitted_drafts(self):
        node = graphql_pr(
            reviews=[
                graphql_review(1, "APPROVED", "imported-user", "Mannequin"),
                {
                    "state": "PENDING",
                    "fullDatabaseId": None,
                    "author": None,
                    "submittedAt": None,
                },
            ],
            requests=[
                {
                    "requestedReviewer": {
                        "__typename": "Mannequin",
                        "login": "imported-request",
                    }
                }
            ],
        )
        complete_review_pages("example/repo", [node])
        pr = matrix.resolve_graphql_pr("example/repo", node)
        self.assertEqual(matrix.cell(pr, matrix.Reviewer("imported-user")), "💚")
        self.assertEqual(matrix.cell(pr, matrix.Reviewer("imported-request")), "🟠")
        self.assertEqual(len(pr.reviewers), 2)

    def test_authored_only_preserves_bot_login_convention(self):
        node = graphql_pr()
        node["author"] = {"__typename": "Bot", "login": "robot"}
        with patch.object(
            matrix.GitHub,
            "json",
            return_value={"data": {"repository": {"pullRequests": connection([node])}}},
        ):
            prs = fetch_prs("example/repo", "open", "robot[bot]", authored_only=True)
        self.assertEqual([pr.author for pr in prs], ["robot[bot]"])

    def test_overflow_queries_stay_bounded(self):
        nodes = [graphql_pr(i) for i in range(matrix.PR_BATCH_SIZE + 1)]
        for node in nodes:
            node["reviews"] = connection([], f"cursor-{node['number']}")

        def fetch(repo, fields):
            numbers = [n["number"] for n in nodes if f"p{n['number']}:" in fields]
            self.assertLessEqual(len(numbers), matrix.PR_BATCH_SIZE)
            return {
                f"p{number}": {
                    "reviews": connection([graphql_review(number, "APPROVED")])
                }
                for number in numbers
            }

        with patch.object(matrix.GitHub, "repository", side_effect=fetch) as api:
            complete_review_pages("example/repo", nodes)
        self.assertEqual(api.call_count, 2)
        self.assertTrue(all(len(node["reviews"]) == 1 for node in nodes))

    @trio_test
    async def test_repository_and_user_discovery_overlap(self):
        repo_started, user_started = anyio.Event(), anyio.Event()

        async def repo_lookup(host):
            repo_started.set()
            await user_started.wait()
            return "example/repo"

        async def json_request(*args, **kwargs):
            self.assertEqual(args, ("GET", "/user"))
            user_started.set()
            await repo_started.wait()
            return {"login": "author"}

        with (
            patch.object(matrix, "current_repository", side_effect=repo_lookup),
            patch.object(matrix.GitHub, "json", side_effect=json_request),
            patch.object(matrix, "fetch_prs", return_value=[]),
        ):
            report = await matrix.build_report(report_args(repo=None, user=None))
        self.assertIn("example/repo", report)
        self.assertIn("user: author", report)

    @trio_test
    async def test_repositories_overlap_and_preserve_output_order(self):
        a_started, b_finished = anyio.Event(), anyio.Event()
        clients = []

        async def fetch(github, repo, *_args):
            clients.append(github)
            if repo == "example/a":
                a_started.set()
                await b_finished.wait()
            else:
                await a_started.wait()
                b_finished.set()
            return [matrix.resolve_pr(repo, raw_pr(), [])]

        with patch.object(matrix, "fetch_prs", side_effect=fetch):
            report = await matrix.build_report(
                report_args(repo=["example/a", "example/b"])
            )
        self.assertIs(clients[0], clients[1])
        self.assertLess(report.index("[example/a#7]"), report.index("[example/b#7]"))

    @trio_test
    async def test_global_request_limit(self):
        full, release = anyio.Event(), anyio.Event()
        active = peak = 0

        async def handle(request):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            if active == matrix.MAX_REQUESTS:
                full.set()
            try:
                await release.wait()
                return httpx.Response(200, json={})
            finally:
                active -= 1

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            github = matrix.GitHub(http)

            async def requests():
                await matrix.concurrent_results(
                    *(
                        partial(github.json, "GET", "/user")
                        for _ in range(matrix.MAX_REQUESTS + 3)
                    )
                )

            async with anyio.create_task_group() as tasks:
                tasks.start_soon(requests)
                await full.wait()
                self.assertEqual(active, matrix.MAX_REQUESTS)
                release.set()
        self.assertEqual(peak, matrix.MAX_REQUESTS)
        self.assertEqual(active, 0)

    @trio_test
    async def test_pr_pagination_overlaps_nested_pagination_and_continues_past_two(
        self,
    ):
        outer, nested = anyio.Event(), anyio.Event()
        calls = []

        async def repository(repo, fields):
            calls.append(fields)
            if "pullRequests" in fields:
                if 'after:"outer-2"' in fields:
                    return {"pullRequests": connection([graphql_pr(3)])}
                if 'after:"outer-1"' in fields:
                    outer.set()
                    await nested.wait()
                    return {"pullRequests": connection([graphql_pr(2)], "outer-2")}
                node = graphql_pr(1, reviews=[graphql_review(1, "APPROVED")])
                node["reviews"]["pageInfo"] = {
                    "hasNextPage": True,
                    "endCursor": "review-1",
                }
                return {"pullRequests": connection([node], "outer-1")}
            if 'after:"review-1"' in fields:
                nested.set()
                await outer.wait()
                return {
                    "p1": {
                        "reviews": connection(
                            [graphql_review(2, "COMMENTED")], "review-2"
                        )
                    }
                }
            self.assertIn('after:"review-2"', fields)
            return {
                "p1": {"reviews": connection([graphql_review(3, "CHANGES_REQUESTED")])}
            }

        with patch.object(matrix.GitHub, "repository", side_effect=repository):
            prs = await matrix.fetch_prs(
                matrix.GitHub(None), "example/repo", "open", "author"
            )
        self.assertEqual([pr.number for pr in prs], [1, 2, 3])
        self.assertEqual(matrix.cell(prs[0], matrix.Reviewer("j3m7")), "🟥")
        self.assertEqual(len(calls), 5)

    @trio_test
    async def test_independent_overflow_batches_overlap(self):
        nodes = [graphql_pr(i) for i in range(2)]
        for node in nodes:
            node["reviews"] = connection([], f"cursor-{node['number']}")
        first, second = anyio.Event(), anyio.Event()

        async def repository(repo, fields):
            if "p0:" in fields:
                first.set()
                await second.wait()
                return {"p0": {"reviews": connection([graphql_review(1, "APPROVED")])}}
            second.set()
            await first.wait()
            return {
                "p1": {"reviews": connection([graphql_review(1, "CHANGES_REQUESTED")])}
            }

        with (
            patch.object(matrix, "PR_BATCH_SIZE", 1),
            patch.object(matrix.GitHub, "repository", side_effect=repository),
        ):
            await matrix.complete_review_pages(
                matrix.GitHub(None), "example/repo", nodes
            )
        self.assertEqual(
            [n["reviews"][0]["state"] for n in nodes], ["APPROVED", "CHANGES_REQUESTED"]
        )

    def test_task_failure_cancels_inflight_request_and_prints_no_partial_output(self):
        cancelled = []
        started = None
        original_build = matrix.build_report

        async def repo_lookup(host):
            await started.wait()
            raise matrix.ReportError("Repository discovery failed")

        async def request(*args, **kwargs):
            started.set()
            try:
                await anyio.sleep_forever()
            finally:
                cancelled.append(True)

        async def build(_args):
            nonlocal started
            started = anyio.Event()
            with anyio.fail_after(5):
                return await original_build(report_args(repo=None, user=None))

        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(matrix, "current_repository", side_effect=repo_lookup),
            patch.object(matrix.httpx.AsyncClient, "request", side_effect=request),
            patch.object(matrix, "build_report", side_effect=build),
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            status = matrix.main([])
        self.assertEqual(status, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("Repository discovery failed", errors.getvalue())
        self.assertTrue(cancelled)

    @trio_test
    async def test_direct_http_graphql_variables_and_authentication(self):
        requests = []

        async def handle(request):
            requests.append(request)
            return httpx.Response(200, json={"data": {"repository": {"name": "repo"}}})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle),
            headers={"Authorization": "Bearer test-token"},
        ) as http:
            github = matrix.GitHub(http)
            result = await github.repository("example/repo", "name")
        self.assertEqual(result, {"name": "repo"})
        self.assertEqual(str(requests[0].url), "https://api.github.com/graphql")
        self.assertEqual(requests[0].method, "POST")
        self.assertEqual(requests[0].headers["Authorization"], "Bearer test-token")
        body = json.loads(requests[0].content)
        self.assertEqual(body["variables"], {"owner": "example", "name": "repo"})

    @trio_test
    async def test_http_errors_and_invalid_json_fail_without_credentials_in_error(self):
        for response in (
            httpx.Response(401, text="test-token"),
            httpx.Response(200, text="invalid-json"),
        ):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda request, response=response: response
                )
            ) as http:
                with self.assertRaises(matrix.ReportError) as error:
                    await matrix.GitHub(http).json("GET", "/user")
                self.assertNotIn("test-token", str(error.exception))

    @trio_test
    async def test_token_source_precedence_and_local_credential_lookup(self):
        with (
            patch.dict(
                os.environ,
                {"GH_TOKEN": "preferred", "GITHUB_TOKEN": "secondary"},
                clear=True,
            ),
            patch.object(matrix.anyio, "run_process") as process,
        ):
            self.assertEqual(await self.real_credentials("github.com"), "preferred")
            process.assert_not_called()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(
                matrix.anyio,
                "run_process",
                return_value=CompletedProcess([], 0, b"stored-token\n", b""),
            ) as process,
        ):
            self.assertEqual(await self.real_credentials("github.com"), "stored-token")
            self.assertEqual(
                process.call_args.args[0],
                ["gh", "auth", "token", "--hostname", "github.com"],
            )
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(
                matrix.anyio,
                "run_process",
                return_value=CompletedProcess([], 1, b"", b"private diagnostic"),
            ),
            self.assertRaises(matrix.ReportError) as error,
        ):
            await self.real_credentials("github.com")
        self.assertNotIn("private diagnostic", str(error.exception))

    def test_local_repository_url_forms(self):
        for remote in (
            "https://github.com/example/repo.git",
            "git@github.com:example/repo.git",
            "ssh://git@github.com/example/repo.git",
            "example/repo",
            "github.com/example/repo",
        ):
            self.assertEqual(
                matrix.repository_name(remote, "github.com"), "example/repo"
            )
        with self.assertRaises(matrix.ReportError):
            matrix.repository_name(
                "https://elsewhere.example/example/repo.git", "github.com"
            )

    @trio_test
    async def test_repository_discovery_is_local_and_honors_override(self):
        with (
            patch.dict(os.environ, {"GH_REPO": "example/override"}, clear=True),
            patch.object(matrix.anyio, "run_process") as process,
        ):
            self.assertEqual(
                await matrix.current_repository("github.com"), "example/override"
            )
            process.assert_not_called()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(
                matrix.anyio,
                "run_process",
                side_effect=[
                    CompletedProcess(
                        [], 0, b"", b"No default remote repository has been set"
                    ),
                    CompletedProcess([], 0, b"git@github.com:example/repo.git\n", b""),
                ],
            ) as process,
        ):
            self.assertEqual(
                await matrix.current_repository("github.com"), "example/repo"
            )
            self.assertEqual(
                process.call_args.args[0], ["git", "remote", "get-url", "origin"]
            )
            self.assertEqual(
                process.call_args_list[0].args[0],
                ["gh", "repo", "set-default", "--view"],
            )
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(
                matrix.anyio,
                "run_process",
                return_value=CompletedProcess(
                    [], 0, b"github.com/example/upstream\n", b""
                ),
            ) as process,
        ):
            self.assertEqual(
                await matrix.current_repository("github.com"), "example/upstream"
            )
            self.assertEqual(process.call_count, 1)

    def test_no_rich_outputs_plain_markdown(self):
        report = matrix.render(
            [matrix.resolve_pr("example/repo", raw_pr(), [])], {}, "author"
        )
        for options in (["--no-rich"], ["--rich", "--no-rich"]):
            output = io.StringIO()
            with (
                self.subTest(options=options),
                patch.object(matrix, "build_report", return_value=report),
                redirect_stdout(output),
            ):
                self.assertEqual(matrix.main(options), 0)
            self.assertEqual(output.getvalue(), report + "\n")

    def test_default_and_explicit_rich_render_table_and_clickable_pr(self):
        from rich.console import Console

        pr = matrix.resolve_pr("example/repo", raw_pr(["j3m7"]), [])
        report = matrix.render([pr], {"j3m7": "j"}, "author")
        for options in ([], ["--rich"], ["--no-rich", "--rich"]):
            output = io.StringIO()
            console = Console(
                file=output,
                width=200,
                force_terminal=True,
                color_system="standard",
                record=True,
            )
            with (
                self.subTest(options=options),
                patch.object(matrix, "build_report", return_value=report),
                patch("rich.console.Console", return_value=console),
            ):
                self.assertEqual(matrix.main(options), 0)
            text = console.export_text()
            for literal in (
                "#7",
                "Authoring",
                "A | title [with] `markup` and lines",
                "Pending requests",
                "🟠",
                "Q",
            ):
                self.assertIn(literal, text)
            self.assertNotIn(":---:", text)
            self.assertNotIn("[#7]", text)
            self.assertIn("\x1b]8;", output.getvalue())
            self.assertIn(pr.url, output.getvalue())

    def test_rich_failure_keeps_stdout_empty(self):
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(
                matrix,
                "build_report",
                side_effect=matrix.ReportError("API unavailable"),
            ),
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            self.assertEqual(matrix.main(["--rich"]), 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("API unavailable", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
