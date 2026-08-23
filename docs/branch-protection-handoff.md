# Branch-protection handoff

## Required operator action

**Status: unverified control-plane action.** Repository YAML cannot configure or
prove GitHub branch protection. In GitHub repository settings, protect the
default branch (`main`) and enable **Require status checks to pass before
merging**. Add the exact required check named:

`Pull request CI / deterministic-safety-net`

Also enable **Require branches to be up to date before merging** so the required
check applies to the merge result. Keep the Pages deployment workflow out of the
required-status-check list: it runs after a push and cannot prove that CI was
required before the push.

## Verification evidence to record

An administrator must verify this setting in the GitHub branch-protection UI or
with an authenticated read-only branch-protection API response, then record the
observed check name and timestamp in an operator change record. This repository
does not currently contain that control-plane evidence.
