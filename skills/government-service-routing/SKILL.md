---
name: government-service-routing
description: Route government service questions to the correct read-only system, knowledge source, or approved web source. Use for applications, cases, services, status, eligibility, and procedures.
---

# Government Service Routing

Choose the narrowest authoritative capability for the user's task.

## Routing Order

1. Use enterprise knowledge for policy, requirements, eligibility, and procedures.
2. Use government systems tools for the user's application, case, account, or transaction status.
3. Use Work IQ only for authorized employee context and only in the signed-in user's context.
4. Use approved web search for current public regulations or information not available internally.
5. Use workflow actions only when the user explicitly requests a transaction.

## Instructions

- Use `tool_search` when the appropriate capability is not already visible.
- Never send personal or confidential data to web search.
- Do not claim access to records that the selected tool did not return.
- Preserve identifiers exactly when calling systems, but mask unnecessary identifiers in responses.
- If more than one entity could own the service, ask the user to identify the entity before calling a tool.
- For a failed system call, report the failure and a safe official next step; do not fabricate status.