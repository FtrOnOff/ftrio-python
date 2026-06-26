# Releasing

How to cut a release of `ftrio` to PyPI. Publishing is automated by
`.github/workflows/publish.yml` using PyPI **Trusted Publishing** (OIDC): a
published GitHub Release builds the distributions and uploads them, with no API
tokens or secrets.

## One-time setup (reference)

These are configured once and reused for every release. Verify they are in place
before the first publish:

| Side | Setting | Value |
|---|---|---|
| PyPI pending/trusted publisher | PyPI Project Name | `ftrio` |
| PyPI pending/trusted publisher | Owner | `FtrOnOff` (the **GitHub** owner, must match the repo) |
| PyPI pending/trusted publisher | Repository name | `ftrio-python` |
| PyPI pending/trusted publisher | Workflow name | `publish.yml` |
| PyPI pending/trusted publisher | Environment name | `pypi` |
| GitHub repo | Environment | `pypi` exists (Settings -> Environments) |
| GitHub `pypi` environment | Required reviewers | a release approver (e.g. yourself) |
| GitHub `pypi` environment | Deployment tags | restricted to `v*` |

Notes:

- The PyPI publisher **Owner** is a GitHub identity and must equal the owner of
  the repo the workflow runs from; it is *not* the PyPI organization name, even if
  they happen to share a value.
- To have the project owned by a PyPI organization, create the publisher under the
  organization (once approved) or publish under a personal account and transfer
  the project to the organization afterwards.

### Branch and tag protection

Two rulesets (Settings -> Rules -> Rulesets) protect the release path. Add
**Repository admin** to each ruleset's bypass list so a solo maintainer keeps an
escape hatch and can still create release tags.

- **`protect-main`** (branch ruleset, targets the default branch): require the CI
  status checks (`test (3.11)`, `test (3.12)`, `test (3.13)`) to pass and be up to
  date, require a pull request (0 approvals for a solo maintainer), block force
  pushes, and restrict deletions.
- **`protect-release-tags`** (tag ruleset, targets `v*`): restrict updates and
  deletions so a published release tag can never be moved or removed, and
  optionally restrict creations to maintainers.

These are independent of, and complementary to, the `pypi` environment's `v*`
deployment rule: the rulesets govern who can change branches and tags, the
environment rule governs which tags may publish.

## Cutting a release (checklist)

1. **Confirm `main` is green.** The CI workflow must pass (ruff, mypy, pytest).

   ```console
   ruff check ftrio playground tests && mypy ftrio && pytest
   ```

2. **Bump the version in one place:** `pyproject.toml` -> `[project] version`.

   That is the single source of truth. `ftrio.__version__` is derived from it at
   runtime via the installed package metadata (`importlib.metadata`), so there is
   nothing else to edit. The built sdist/wheel always carry the bumped version.

   Follow [SemVer](https://semver.org): patch for fixes, minor for backward-
   compatible features, major for breaking changes.

   Local note: an editable install caches the version in its metadata at install
   time, so after bumping `pyproject.toml` re-run `pip install -e .` if you want
   `ftrio.__version__` to reflect the new value in your dev checkout. This does not
   affect releases, which build the distributions fresh from `pyproject.toml`.

3. **Update `CHANGELOG.md`.** Move the items under `## [Unreleased]` into a new
   `## [X.Y.Z] - YYYY-MM-DD` section (use the real release date), and refresh the
   comparison links at the bottom.

4. **Commit** the version bump and changelog on `main` (via PR if the branch is
   protected).

   ```console
   git commit -am "Release vX.Y.Z"
   ```

5. **Tag and push.** The tag must start with `v` to satisfy the environment's
   `v*` deployment rule.

   ```console
   git tag vX.Y.Z
   git push origin main --tags
   ```

6. **Create the GitHub Release.** From the tag (Releases -> Draft a new release ->
   choose `vX.Y.Z`). Paste the changelog section as the notes and publish it. This
   is what triggers `publish.yml`.

7. **Approve the deployment.** The `build` job runs, then the `publish` job pauses
   at the `pypi` environment for required-reviewer approval. Open the workflow run
   in the **Actions** tab and approve it. The upload to PyPI then proceeds.

8. **Verify.** Confirm the new version is live and installable:

   ```console
   pip index versions ftrio        # shows the published versions
   pip install "ftrio==X.Y.Z"
   ```

## Dry run (no publish)

Use the workflow's manual trigger to build and `twine check` the distributions
without uploading: **Actions -> Publish to PyPI -> Run workflow**. The `publish`
job is skipped on a manual run (it only runs on a real Release event), so this
validates the build in isolation.

## Troubleshooting

- **Upload rejected / identity mismatch**: the PyPI publisher **Owner** /
  **Repository** / **Workflow** / **Environment** must exactly match the run.
  The most common cause is the Owner not matching the GitHub repo owner.
- **Deployment never starts**: check the tag matches the `v*` environment rule and
  that the Release event fired the workflow.
- **Name already taken**: `ftrio` is a global PyPI name; if it is claimed by
  someone else, rename the distribution in `pyproject.toml`.
