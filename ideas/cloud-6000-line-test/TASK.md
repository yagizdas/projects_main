# Verify a 6,000-line patch handoff

Use this short Python command to generate `fixture.txt` beside this task file. Do not type or print the generated lines.

```python
from pathlib import Path
Path('ideas/cloud-6000-line-test/fixture.txt').write_bytes(''.join(f'{i:06d} cloud-patch-fixture\n' for i in range(1, 6001)).encode('ascii'))
```

Verify there are exactly 6,000 lines and compute the SHA-256 of the file. Delete this TASK.md, commit only these two changes in the Cloud workspace, and leave the patch in the task. In the GitHub reply report only line count, SHA-256, the Cloud task link and the exact completion marker from the request. Do not paste the diff or generated lines and do not push or create another PR.
