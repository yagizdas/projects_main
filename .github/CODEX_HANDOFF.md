# Claude to Codex handoff

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
