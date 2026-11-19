# Branch protection runbook

Settings the repository owner applies in GitHub to protect `master`. They are
not stored in the repository, so nothing here takes effect until the owner
applies it under Settings, Rules, Rulesets (or Settings, Branches).

Railway deploys `master` once its workflows pass (Wait for CI, see
[Railway deploys](#railway-deploys)), so a change that reaches
`master` is in production once its checks pass. The rules below keep
unreviewed or unchecked changes out.

## Required status checks

A required check is matched by its **job name**, not by the workflow name. When
a job has no `name:` key, GitHub uses the job id. GitHub's checks list shows
each one as `<workflow> / <job>`; enter only the job name in the rule.

These workflows run on every pull request to `master`:

| Workflow (`name:`) | Job name to require | Shown in the checks list as | Notes |
| --- | --- | --- | --- |
| `pre-commit` | `pre-commit-alls-green` | `pre-commit / pre-commit-alls-green` | Gate over the `pre-commit` job. |
| `Test Backend` | `test-backend` | `Test Backend / test-backend` | Lint, types, Pytest with the 87% branch-coverage floor, deployment helper tests. |
| `Edge CI` | `frontend-and-edge` | `Edge CI / frontend-and-edge` | Biome, frontend build, Cloudflare Worker tests. |
| `Railway CI` | `workflow-lint` | `Railway CI / workflow-lint` | Runs actionlint on every workflow with shellcheck installed. |
| `Railway CI` | `railway-config` | `Railway CI / railway-config` | Type-checks the Railway infrastructure with the locked SDK. |
| `Railway CI` | `railway-image-backend` | `Railway CI / railway-image-backend` | Builds and smoke-tests the backend production image. |
| `Railway CI` | `railway-image-ingestion` | `Railway CI / railway-image-ingestion` | Builds and smoke-tests the ingestion worker image. |
| `Playwright Tests` | `alls-green-playwright` | `Playwright Tests / alls-green-playwright` | Gate over `typecheck`, `test-mocked` and `test-playwright`. Passes when a pull request touches none of the filtered paths, because the jobs are then skipped. |
| `Test Docker Compose` | `test-docker-compose` | `Test Docker Compose / test-docker-compose` | Builds the Compose stack and checks that it starts. |
| `Zizmor` | `Run zizmor` | `Zizmor / Run zizmor` | Static analysis of the workflow files. This job sets `name: Run zizmor`, so the space is part of the name. |

Require `pre-commit-alls-green` and `alls-green-playwright` instead of the jobs
behind them. The gate jobs run even when an upstream job is skipped or fails,
so the rule never waits on a check that does not exist.

Other jobs that appear on pull requests, and why they are not required:

| Workflow | Job name | Why it is not required |
| --- | --- | --- |
| `Playwright Tests` | `changes`, `typecheck`, `test-mocked`, `test-playwright`, `merge-playwright-reports` | Skipped when no filtered path changed; `alls-green-playwright` reports their result. `merge-playwright-reports` only publishes a report. |
| `pre-commit` | `pre-commit` | Covered by `pre-commit-alls-green`. |
| `Conflict detector` | `main` | Runs on `pull_request_target` for `synchronize` events only and labels pull requests with merge conflicts. It reports no verdict on the code. |
| `Guard Dependencies` | `check-author` | Runs only when a lockfile or `pyproject.toml` changes. It closes the pull request itself when a non-maintainer changes them. |

`push` runs on `master` repeat `Test Backend`, `Edge CI`, `Railway CI`,
`Playwright Tests`, `Test Docker Compose`, `Zizmor` and `Conflict detector`; those results are not
part of the rule.

The Render image job, `production-container`, has been deleted; remove it from
the required checks if the rule still lists it, or pull requests wait on it
forever. Deployment files, Compose files and Dockerfiles are included in the
Playwright path filter.

Keep this table in step with `.github/workflows/`. If a job is renamed or a new
workflow is added, update the required list in the same change, or the pull
request waits forever on a check name that no longer exists.

## Railway deploys

Every Railway service in `deployment/railway/railway.ts` sets
`checkSuites: true`, Railway's **Wait for CI**. Confirm the toggle shows as on
in each service's settings, after accepting the Railway GitHub app's updated
permissions. With it, Railway deploys a commit on `master` only after
the GitHub Actions workflows that run on that commit have finished:

- It judges whole workflow runs, not jobs, and ignores checks from other
  GitHub apps. Branch protection's required checks do not change which runs it
  waits for.
- One failed workflow skips the deploy at once; skipped and neutral runs never
  block; a cancelled run blocks only if no other run on the commit succeeded;
  runs that have not finished within two hours skip the deploy.
- Only workflows with a `push` trigger on `master` run on the commit. Today
  these are `Test Backend`, `Edge CI`, `Railway CI`, `Playwright Tests`,
  `Test Docker Compose`, `Zizmor` and `Conflict detector`. `pre-commit` runs on
  pull requests only, so it gates merging but not deploying.
- `Conflict detector` labels other pull requests; a failure there (for
  example a GitHub API error) also skips the deploy. Re-run it, or use
  Deploy Latest Commit in Railway.
- Every workflow uses `cancel-in-progress` per branch, so when two commits
  land close together the older commit's runs are cancelled and its deploy is
  skipped; the newer commit deploys once its runs pass.

Migrations do not depend on Wait for CI: they run as the `api` service's
pre-deploy command for each deploy.

## Rule settings for `master`

- **Require a pull request before merging.** Required approvals: `0` while the
  owner is the only maintainer (GitHub does not let an author approve their
  own pull request); raise it to `1` when a second maintainer joins. Dismiss
  stale approvals on new commits.
- **Require status checks to pass**, with the job names in the first table, and
  **require branches to be up to date before merging**.
- **Require linear history.** This permits squash and rebase merges and blocks
  merge commits. In Settings, General, Pull Requests, turn off "Allow merge
  commits", and turn on "Automatically delete head branches".
- **Block force pushes** and **restrict deletions**, for everyone, with the one
  exception below.
- **Do not allow bypassing** the rule for other people. Leave the owner's
  bypass off as well, except during the history rewrite.
- Do not enable "Require signed commits": the history is unsigned.

### Ruleset equivalent

The same rule as a repository ruleset. Apply it under Settings, Rules,
Rulesets, "Import a ruleset":

```json
{
  "name": "protect-master",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/heads/master"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_linear_history" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "pre-commit-alls-green" },
          { "context": "test-backend" },
          { "context": "frontend-and-edge" },
          { "context": "production-container" },
          { "context": "workflow-lint" },
          { "context": "railway-config" },
          { "context": "railway-image-backend" },
          { "context": "railway-image-ingestion" },
          { "context": "alls-green-playwright" },
          { "context": "test-docker-compose" },
          { "context": "Run zizmor" }
        ]
      }
    }
  ],
  "bypass_actors": []
}
```

## History rewrite: the one allowed force-push

Publishing the repository needs a one-time rewrite of `master` (author
addresses, commit trailers and removed paths). That push is the only force-push
the rules allow, and only the owner makes it.

1. Do the rewrite on a fresh mirror clone, never in this checkout.
2. Do it **before** applying the ruleset above. If the ruleset is already
   active, add the owner as a bypass actor (Rulesets, Bypass list, "Always
   allow"), or set the ruleset's enforcement to "Disabled".
3. Push `master` once with `git push --force-with-lease origin master`. Render
   rebuilds from the new head when the checks pass.
4. Remove the bypass actor, or set enforcement back to "Active", and confirm
   with `gh api repos/{owner}/{repo}/rulesets` that `non_fast_forward` is
   enforced and the bypass list is empty.

Open pull requests and every other branch need rebasing onto the rewritten
history, or deleting.

## Labels

`.github/dependabot.yml` and `.github/workflows/detect-conflicts.yml` apply
labels that GitHub does not create on its own. Create them once:

```sh
gh label create dependencies --color 0366d6 --description "Dependency updates"
gh label create python --color 3572a5 --description "Python dependency updates"
gh label create javascript --color f1e05a --description "JavaScript dependency updates"
gh label create github_actions --color 000000 --description "GitHub Actions updates"
gh label create docker --color 0db7ed --description "Docker image updates"
gh label create conflicts --color b60205 --description "Pull request has merge conflicts"
```

## Other repository settings

- Settings, Actions, General: set the default workflow token to read-only (the
  workflows request the permissions they need) and require approval for
  workflow runs from outside collaborators.
- Settings, Code security: enable Dependabot alerts and security updates, and
  secret scanning with push protection.
- Settings, Tags: protect `v*` tags if releases are tagged.
