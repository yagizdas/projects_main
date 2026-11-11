# Claude to Codex handoff

Use the Cloud task publisher when it is running on the signed-in Mac. Claude
should commit `ideas/<project>/TASK.md` to a branch in this repository and open
a PR to `main` as the repository owner. Generate a unique 32-character
lowercase hexadecimal request ID. Start the PR title with
`[codex:<request-id>] ` followed by a short title. Use the current full PR
head SHA and the same request ID in a top-level PR comment.

```text
@codex Implement ideas/<project>/TASK.md at <head-sha> and run the relevant tests.
CODEX_PATCH_REQUEST <request-id> <head-sha> ideas/<project>/TASK.md

Keep changes inside ideas/<project>/. Remove TASK.md when done. Keep the
changes in the Cloud task diff. After completing and testing the work, reply
with a brief summary, a link to the Cloud task, and the exact line below
with the placeholders replaced. Do not paste a diff or push from Cloud.

CODEX_CLOUD_READY <request-id> <head-sha>
```

The Mac publisher checks the request and Codex's reply, looks up the
matching completed task through the signed-in Codex CLI, and pushes the
validated patch to the same PR branch. The Mac must be awake and logged in.
For a retry, update the PR title with a fresh request ID before posting a new
request with the current head SHA.

## Comment diff with GitHub Actions

Tell Claude to commit the task spec at `ideas/<project>/TASK.md`, push it to a
branch in this repository, and open a PR to `main` from the repository owner's
GitHub account. Have Claude get the full current PR head SHA and generate a
unique 32-character lowercase hexadecimal request ID. Use those values in a
top-level PR comment.

````text
@codex Implement ideas/<project>/TASK.md at <head-sha> and run the relevant tests.
CODEX_PATCH_REQUEST <request-id> <head-sha> ideas/<project>/TASK.md

Keep all changes in ideas/<project>/. Remove TASK.md when done. Include new and
deleted files by using git diff --binary <head-sha> HEAD after committing your
changes in the workspace. Reply using the exact marker lines below, replacing
the placeholders with the values above. Put the patch in one diff block and do
not add blank lines between the markers and the block. Put the test summary
outside this block.

CODEX_PATCH_RESULT <request-id> <head-sha>
```diff
<complete git diff beginning with diff --git>
```
CODEX_PATCH_END <request-id>

If the complete diff will not fit in one GitHub comment, report that and link
the Cloud task instead of replying with a partial patch.
````

The **Publish Codex patch** workflow verifies the author and request, then
applies the patch against the approved commit and pushes to the PR branch.
If the branch changes first, have Claude post a new request with the updated
head SHA and a new request ID. See the Actions run for validation errors.

For an oversized patch, open the linked Cloud task and publish from there if
that option is available, or apply the Cloud diff to an authenticated local
checkout with `codex apply TASK_ID` and push from there.
