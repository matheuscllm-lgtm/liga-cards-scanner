# Security

This is a personal, single-user project. It is published mainly to use free CI.

## Reporting

If you believe you have found a security issue (for example, a credential that
was accidentally committed), **do not open a public issue, pull request or
discussion that contains the secret value.** Public issues are world-readable
and would expose the secret further.

Instead, contact the maintainer privately and include only the minimum needed to
locate the problem (file path and line, never the full secret value).

## Secrets handling

- This project needs no API keys to run its default and live paths; the only
  configuration is a numeric conversion rate.
- Any credentials, if ever added, must be read from environment variables or a
  local config file (`scanner.config`), never hard-coded.
- `scanner.config` and any data/state files are git-ignored and must never be
  committed; `scanner.config.example` contains variable names only.
- The browser used by the live data path runs against a profile stored in the
  user's home directory, **outside** this repository — it is never committed.
- CI uses repository **Secrets** (`Settings → Secrets and variables → Actions`)
  if ever needed; secrets are never written into workflow files or printed to
  logs. The test workflow uses no secrets at all.

## If a secret is ever exposed

1. **Rotate it immediately** at the provider (the old value is considered
   compromised the moment it touches a public repo — clones and caches persist).
2. Remove it from the working tree and history.
3. Replace the CI secret with the new value.
