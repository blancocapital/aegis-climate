# TRACEABILITY MATRIX (MVP)

Links functional requirements to planned implementations (endpoints/jobs/tables/tests/UI). Source: `docs/mvp-technical-specification.md` and `docs/mvp-prd.md`.

| Requirement | Backend endpoint/job | Data model | UI Surface | Tests |
| --- | --- | --- | --- | --- |
| Exposure upload/mapping/validation/commit | /uploads, /uploads/{id}/mapping, /uploads/{id}/validate (job), /uploads/{id}/commit | exposure_upload, mapping_template, validation_result, exposure_version, location/account/policy | Upload & Mapping, Validation summary | Unit: mapping/validation; Integration: upload flow |
| Geocode + quality scoring + exceptions | geocode job (VALIDATION/GEOCODE run), exceptions endpoint | location.geocode_method/confidence, quality_tier, quality_reasons_json | Exceptions queue | Unit: quality scoring; Integration: exceptions scope |
| Hazard datasets + overlays | /hazard-overlays (job), /hazard-overlays/{id}/status/summary | hazard_dataset, hazard_dataset_version, hazard_overlay_result, location_hazard_attribute | Overlay status | Unit: overlay join |
| Rollups + drilldown | /rollup-configs, /rollups, /rollups/{id}, /rollups/{id}/drilldown | rollup_config, rollup_result | Accumulation dashboard | Unit: rollup aggregation; Integration: rollup endpoints |
| Threshold rules + breaches workflow | /threshold-rules, /breaches/run, /breaches, /breaches/{id} PATCH | threshold_rule, breach | Threshold builder + breach list | Unit: threshold evaluation; Integration: breach workflow |
| Drift report | /drift (job), /drift/{id}, /drift/{id}/details | drift_run, drift_detail | Drift report page | Unit: drift classification; Integration: drift endpoints |
| Governance runs + lineage | /runs/{id}, /lineage | run | Governance: Runs/Lineage | Integration: lineage correctness |
| Audit log | /audit-events | audit_event | Audit log viewer | Integration: audit visibility |
| Golden determinism | pipeline executions recorded via run with checksums | run.artifact_checksums_json | Governance views | Determinism/golden dataset tests |
