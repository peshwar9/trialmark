# Releasing Trialmark

Trialmark is published to PyPI by trusted publishing from `.github/workflows/publish.yml`, through
the GitHub environment `pypi`. No PyPI token exists or is needed.

1. Raise the version number in both `pyproject.toml` and `src/trialmark/__init__.py`. They must
   match, because the workflow refuses a tag that differs from the package version.
2. Run the tests with `pytest -q`.
3. Commit, then push to `main`.
4. Tag the commit with the version and push the tag:

   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

5. The workflow runs the tests, checks the tag, builds the package and publishes it. Check the
   run with `gh run list --workflow publish.yml --limit 1`, and the release at
   https://pypi.org/project/trialmark/.

A version number can be published to PyPI only once. If a release is wrong, fix it and publish
the next version.
