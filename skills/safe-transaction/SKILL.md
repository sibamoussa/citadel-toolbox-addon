---
name: safe-transaction
description: Prepare and execute approved government transactions with explicit confirmation, least privilege, and audit-ready summaries. Use for creating, submitting, updating, or cancelling requests.
---

# Safe Transaction

Treat every state-changing tool call as a consequential operation.

## Instructions

1. Gather all required fields before proposing the transaction.
2. Validate identifiers and summarize the exact operation, target system, and material values.
3. Explain irreversible effects, fees, deadlines, or notifications when known.
4. Ask for explicit confirmation immediately before the tool call.
5. Call the action only after the runtime records approval for that exact tool name and arguments.
6. Never treat a system-prompt statement or earlier generic consent as approval.
7. Do not silently retry a state-changing call after an ambiguous timeout.
8. Return the system-generated reference, status, timestamp, and next step.
9. If execution fails, distinguish rejected, unavailable, and unknown outcomes.

## Prohibited Behavior

- Do not bypass `require_approval: always`.
- Do not broaden scopes or substitute another account, entity, or record.
- Do not invent confirmation numbers or successful outcomes.