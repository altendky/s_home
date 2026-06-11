---
description: Request CodeRabbit review, waiting for rate limits when needed
---

# Request CodeRabbit Review

**PR URL or number (optional):** $1

Request a CodeRabbit review for the provided PR. If CodeRabbit has already
approved the PR, no action is needed. If the latest relevant CodeRabbit comment
says the PR review limit has been reached, wait until more reviews are available
before posting `@coderabbitai review`.

## Process

0. **Check execution permissions before doing any long wait:**
   - Before calculating or sleeping, check whether the current opencode mode, system prompts, tool permissions, or user instructions allow posting the final GitHub comment.
   - If the current mode is read-only, plan-only, or otherwise prevents running the final `gh api ... -f body='@coderabbitai review'` command, warn the user immediately and stop before waiting.
   - The warning must clearly say that the command would be able to wait but would not be allowed to submit the CodeRabbit trigger comment afterward.
   - Ask the user to change mode or permissions, then rerun the command.
   - Do not sleep unless the final comment submission is expected to be permitted.

1. **Identify the PR:**
   - If `$1` is omitted, infer the PR for the current branch with:

     ```sh
     gh pr view --json url --jq .url
     ```

   - If no PR is associated with the current branch, report that no PR could be inferred and ask the user to provide a PR URL or PR number.
   - If `$1` is a GitHub PR URL matching `https://github.com/<owner>/<repo>/pull/<number>`, use it.
   - If `$1` is a bare PR number, use `gh pr view <number> --json url --jq .url` to resolve the full URL for the current repository.
   - If `$1` is provided but is neither a PR URL nor a bare PR number, ask the user for a PR URL or PR number and stop.

2. **Check for existing CodeRabbit approval:**
   - Fetch PR reviews with:

     ```sh
     gh api repos/<owner>/<repo>/pulls/<pr_number>/reviews
     ```

   - If any review authored by CodeRabbit has `state == "APPROVED"`, report the review URL and stop without posting a new comment.

3. **Find the latest CodeRabbit limit comment:**
   - Extract `owner`, `repo`, and `pr_number` from the URL.
   - Fetch PR issue comments with `gh api --paginate --slurp`, then pipe to standalone `jq` for filtering. Do not combine `--slurp` with `--jq`; some `gh` versions reject that combination.

     ```sh
     gh api --paginate --slurp repos/<owner>/<repo>/issues/<pr_number>/comments \
       | jq '[.[][] | select(...)] | sort_by(.updated_at, .created_at) | last'
     ```

   - The unfiltered fetch is:

     ```sh
     gh api --paginate repos/<owner>/<repo>/issues/<pr_number>/comments
     ```

   - Select comments authored by CodeRabbit whose body contains both:
     - `Review limit reached`
     - `More reviews will be available in`
   - Use the latest matching comment by `updated_at`; if tied, use the latest `created_at`.
   - If no matching comment exists, report that no CodeRabbit review-limit comment was found and submit `@coderabbitai review` immediately.

4. **Calculate the wait time:**
   - Use the comment's `updated_at` as the reference time when it differs from `created_at`; otherwise use `created_at`.
   - Parse the duration from the sentence:

     ```text
     More reviews will be available in <duration>.
     ```

   - Support any combination of `day(s)`, `hour(s)`, `minute(s)`, and `second(s)`, including forms like:
     - `19 minutes and 3 seconds`
     - `1 hour and 2 minutes`
     - `45 seconds`
   - Compute:

     ```text
     available_at = reference_time + parsed_duration
     remaining_seconds = available_at - now
     ```

5. **Report before acting:**
   - Print the selected comment URL.
   - Print whether `created_at` or `updated_at` is being used as the reference time.
   - Print the parsed duration.
   - Print the computed `available_at` time.
   - If `remaining_seconds <= 0`, print that the reset time has already passed and the review request will be submitted immediately.
   - If `remaining_seconds > 0`, print the remaining wait and the final wait including the 15 second buffer.

6. **Wait if needed:**
   - If `remaining_seconds <= 0`, do not sleep.
   - If `remaining_seconds > 0`, sleep for `remaining_seconds + 15` seconds.
   - When invoking the shell tool for this command, set its timeout greater than the planned sleep duration plus a small margin. A long `sleep` can otherwise be reported as a tool error even though the script logic is correct.

7. **Request the review:**
   - Post the trigger comment:

     ```sh
     gh api repos/<owner>/<repo>/issues/<pr_number>/comments -f body='@coderabbitai review'
     ```

   - Report the URL of the submitted comment.

## Suggested Implementation

Use this shell script structure from any directory where `gh` is authenticated.
It requires `jq`, `perl`, and GNU `date`.

```sh
input='$1'

if [ -z "$input" ]; then
  pr_url=$(gh pr view --json url --jq .url 2>/dev/null) || {
    printf 'No PR provided and no PR found for the current branch. Provide a GitHub PR URL or PR number.\n' >&2
    exit 1
  }
else
  case "$input" in
    *[!0-9]*) pr_url=$input ;;
    *) pr_url=$(gh pr view "$input" --json url --jq .url) || exit 1 ;;
  esac
fi

case "$pr_url" in
  https://github.com/*/*/pull/[0-9]*) ;;
  *)
    printf 'Provide a GitHub PR URL like https://github.com/owner/repo/pull/123 or a PR number.\n' >&2
    exit 1
    ;;
esac

owner=$(printf '%s\n' "$pr_url" | cut -d/ -f4)
repo=$(printf '%s\n' "$pr_url" | cut -d/ -f5)
pr_number=$(printf '%s\n' "$pr_url" | cut -d/ -f7 | cut -d'#' -f1 | cut -d'?' -f1)

approval_json=$(gh api "repos/$owner/$repo/pulls/$pr_number/reviews" \
  | jq '[.[] | select((.user.login == "coderabbitai[bot]" or .user.login == "coderabbitai") and .state == "APPROVED")] | sort_by(.submitted_at // .submittedAt // "") | last')

if [ -n "$approval_json" ] && [ "$approval_json" != null ]; then
  approval_url=$(printf '%s\n' "$approval_json" | jq -r '.html_url')
  printf 'CodeRabbit has already approved this PR; no review request needed: %s\n' "$approval_url"
  exit 0
fi

comment_json=$(gh api --paginate --slurp "repos/$owner/$repo/issues/$pr_number/comments" \
  | jq '[.[][] | select((.user.login == "coderabbitai[bot]" or .user.login == "coderabbitai") and (.body | contains("Review limit reached")) and (.body | contains("More reviews will be available in")))] | sort_by(.updated_at, .created_at) | last')

if [ -z "$comment_json" ] || [ "$comment_json" = null ]; then
  printf 'No CodeRabbit review-limit comment found on %s; submitting review request immediately.\n' "$pr_url"
  posted=$(gh api "repos/$owner/$repo/issues/$pr_number/comments" -f body='@coderabbitai review')
  posted_url=$(printf '%s\n' "$posted" | jq -r '.html_url')
  printf 'Submitted CodeRabbit review request: %s\n' "$posted_url"
  exit 0
fi

created_at=$(printf '%s\n' "$comment_json" | jq -r '.created_at')
updated_at=$(printf '%s\n' "$comment_json" | jq -r '.updated_at')
comment_url=$(printf '%s\n' "$comment_json" | jq -r '.html_url')
body=$(printf '%s\n' "$comment_json" | jq -r '.body')

if [ "$updated_at" != "$created_at" ]; then
  reference_at=$updated_at
  reference_label=updated_at
else
  reference_at=$created_at
  reference_label=created_at
fi

duration=$(printf '%s\n' "$body" | perl -0ne 'if (/More reviews will be available in\s+(.+?)\./s) { print $1 }')

if [ -z "$duration" ]; then
  printf 'Could not parse CodeRabbit availability duration from %s\n' "$comment_url" >&2
  exit 1
fi

duration_seconds=$(DURATION="$duration" perl -e '
  my $text = lc $ENV{DURATION};
  my %scale = (day => 86400, hour => 3600, minute => 60, second => 1);
  my $total = 0;
  while ($text =~ /(\d+)\s*(day|hour|minute|second)s?/g) {
    $total += $1 * $scale{$2};
  }
  die "no duration units parsed\n" if $total == 0;
  print $total;
') || exit 1

reference_epoch=$(date -u -d "$reference_at" +%s)
now_epoch=$(date -u +%s)
available_epoch=$((reference_epoch + duration_seconds))
remaining_seconds=$((available_epoch - now_epoch))
available_at=$(date -u -d "@$available_epoch" '+%Y-%m-%dT%H:%M:%SZ')

printf 'CodeRabbit limit comment: %s\n' "$comment_url"
printf 'Reference time: %s (%s)\n' "$reference_at" "$reference_label"
printf 'Parsed duration: %s (%s seconds)\n' "$duration" "$duration_seconds"
printf 'More reviews available at: %s\n' "$available_at"

if [ "$remaining_seconds" -gt 0 ]; then
  wait_seconds=$((remaining_seconds + 15))
  printf 'Waiting %s seconds plus 15 second buffer: %s seconds total\n' "$remaining_seconds" "$wait_seconds"
  sleep "$wait_seconds"
else
  printf 'Reset time has already passed; submitting review request immediately.\n'
fi

posted=$(gh api "repos/$owner/$repo/issues/$pr_number/comments" -f body='@coderabbitai review')
posted_url=$(printf '%s\n' "$posted" | jq -r '.html_url')
printf 'Submitted CodeRabbit review request: %s\n' "$posted_url"
```
