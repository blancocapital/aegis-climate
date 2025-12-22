# RBAC Matrix (MVP)

Roles: ADMIN, OPS, ANALYST, AUDITOR, READ_ONLY. Derived from `docs/mvp-technical-specification.md` and `docs/mvp-prd.md`.

| Capability / Endpoint | ADMIN | OPS | ANALYST | AUDITOR | READ_ONLY |
| --- | --- | --- | --- | --- | --- |
| POST /auth/login | ✅ | ✅ | ✅ | ✅ | ✅ |
| Uploads: POST /uploads | ✅ | ✅ | 🚫 | 🚫 | 🚫 |
| Mapping templates: POST /uploads/{id}/mapping | ✅ | ✅ | 🚫 | 🚫 | 🚫 |
| Validation: POST /uploads/{id}/validate | ✅ | ✅ | 🚫 | 🚫 | 🚫 |
| Commit exposure: POST /uploads/{id}/commit | ✅ | ✅ | 🚫 | 🚫 | 🚫 |
| List exposure versions / summaries | ✅ | ✅ | ✅ | ✅ | ✅ |
| Locations / exceptions queries | ✅ | ✅ | ✅ | ✅ | ✅ |
| Geocode + quality pipeline trigger | ✅ | ✅ | ✅ | 🚫 | 🚫 |
| Hazard dataset registry/version create | ✅ | 🚫 | ✅ | 🚫 | 🚫 |
| Hazard overlay execution | ✅ | ✅ | ✅ | 🚫 | 🚫 |
| Rollup config create/update | ✅ | 🚫 | ✅ | 🚫 | 🚫 |
| Rollup execution + drilldown | ✅ | ✅ | ✅ | 🚫 | 🚫 |
| Threshold rule create/update | ✅ | 🚫 | ✅ | 🚫 | 🚫 |
| Breach evaluation run | ✅ | ✅ | ✅ | 🚫 | 🚫 |
| Breach status update | ✅ | ✅ | 🚫 | 🚫 | 🚫 |
| Drift run | ✅ | ✅ | ✅ | 🚫 | 🚫 |
| Governance: runs/lineage read | ✅ | ✅ | ✅ | ✅ | ✅ |
| Audit events read | ✅ | ✅ | ✅ | ✅ | ✅ |
| User/role management | ✅ | 🚫 | 🚫 | 🚫 | 🚫 |

Notes:
- All actions tenant-scoped; roles are per-tenant.
- Sensitive state-changing actions emit audit events.
- READ_ONLY limited to GET endpoints only.
