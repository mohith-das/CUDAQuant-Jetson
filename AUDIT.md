# AUDIT.md — Independent Review Ledger (Codex)

Codex is the **independent external reviewer**. It reviews major milestones separately
from OpenCode and records findings here. At startup the architect reads this file and
prioritizes critical **OPEN** findings before new feature work.

## Statuses
`OPEN` → `IN_PROGRESS` → `FIXED_PENDING_VERIFICATION` → `VERIFIED` | `WONT_FIX`

## Finding template
```
AUDIT-XXX
Severity:            <critical | high | medium | low>
Status:             <OPEN | IN_PROGRESS | FIXED_PENDING_VERIFICATION | VERIFIED | WONT_FIX>
Found by:           <Codex | ...>
Commit inspected:   <hash>

Problem:            <what is wrong>
Evidence:           <file:line, test output, repro>
Required fix:       <what must change>
Resolution:         <what was actually done>
Verified by:        <who/what confirmed the fix>
Verification commit:<hash>
```

## Findings
_(none yet — first audit occurs after Milestone 1/2. Run `/audit-prep` to stage a clean,
pushed commit for Codex.)_
