# Audit Workflow Completion Rule

This process guidance applies to every engineering audit in this repository.

## Completion Gate (Non-Negotiable)

An audit is **not complete** until an `audit-closure` document is published and linked to the originating Kanban audit task.

## Minimum Required Fields in `audit-closure`

- Scope
- Evidence
- Findings
- Task mapping (Finding -> Kanban Task ID -> Status/Owner)
- Residual risk
- Next review date

## Traceability Requirement

- The closure document must include direct mapping from each finding to at least one Kanban task.
- Closure review fails if task mapping or owner/status traceability is missing.

## Template/Checklist Requirement

- Future audit templates and checklists must include the closure gate.
- Reuse `docs/audit-closure-checklist-snippet.md` as the default checklist block.
