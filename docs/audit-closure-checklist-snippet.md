# Audit Closure Checklist Snippet

Use this block in future audit templates/checklists.

```md
## Audit Closure Gate (Mandatory)
- [ ] Audit closure document is created and linked to the audit task ID.
- [ ] Closure doc includes Scope.
- [ ] Closure doc includes Evidence.
- [ ] Closure doc includes Findings.
- [ ] Closure doc includes Task mapping (Finding -> Kanban Task ID -> Status/Owner).
- [ ] Closure doc includes Residual risk.
- [ ] Closure doc includes Next review date.
- [ ] Audit is marked complete only after all closure checks above pass.
```

## Example Closure Documents

- `docs/audit-closures/instagrapi-capability-gap-2026-04-16.md` — closure for the instagrapi-vs-repo capability gap audit (Kanban audit task `68a4d`); demonstrates all six required sections including the Task mapping table with both filed and explicitly deferred findings.
