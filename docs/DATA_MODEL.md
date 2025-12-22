# DATA MODEL (MVP)

Based on `docs/mvp-technical-specification.md` with Postgres + PostGIS. All tables tenant-scoped where applicable.

## Tenancy & Users
- **tenant**(id UUID PK, name, created_at)
- **user**(id UUID PK, tenant_id FK→tenant, email UNIQUE, password_hash, role ENUM[ADMIN,OPS,ANALYST,AUDITOR,READ_ONLY], status, created_at)
  - Index: (tenant_id, email). Immutable history for role changes via audit events.

## Exposure Ingestion
- **exposure_upload**(id UUID PK, tenant_id FK, filename, storage_uri, uploaded_by FK→user, uploaded_at, status, checksum)
- **mapping_template**(id UUID PK, tenant_id FK, name, version INT, mapping_json JSONB, created_by FK→user, created_at)
  - Unique (tenant_id, name, version); immutable rows once created.
- **validation_result**(id UUID PK, upload_id FK→exposure_upload, summary_json JSONB, row_errors_uri, created_at, severity_counts_json)
- **exposure_version**(id UUID PK, tenant_id FK, name, source_upload_id FK→exposure_upload, mapping_template_id FK, created_by FK→user, created_at, immutable BOOLEAN DEFAULT TRUE)
  - Unique (tenant_id, name, created_at); immutable after creation.

## Canonical Entities (partitioned by exposure_version)
- **account**(id UUID PK, tenant_id FK, exposure_version_id FK, external_account_id, name, attributes_json JSONB)
  - Index (tenant_id, exposure_version_id, external_account_id).
- **policy**(id UUID PK, tenant_id FK, exposure_version_id FK, external_policy_id, inception_date, expiry_date, attributes_json JSONB)
  - Index (tenant_id, exposure_version_id, external_policy_id).
- **location**(id UUID PK, tenant_id FK, exposure_version_id FK, external_location_id, address_line1, city, state_region, postal_code, country, lat, lon, geocode_method, geocode_confidence, quality_tier, quality_reasons_json JSONB, tiv NUMERIC, limit NUMERIC, premium NUMERIC, currency, lob, occupancy, construction, year_built INT, policy_id FK→policy NULLABLE, account_id FK→account NULLABLE, updated_at)
  - Indexes: (tenant_id, exposure_version_id), (tenant_id, exposure_version_id, external_location_id UNIQUE), GIST for geography point (lat/lon).
  - Mutability: rows tied to exposure_version immutable post-commit; enrichments tracked via run references.

## Hazard Registry & Overlays
- **hazard_dataset**(id UUID PK, name, peril, vendor, coverage_geo, license_ref, created_at)
- **hazard_dataset_version**(id UUID PK, hazard_dataset_id FK, version_label, storage_uri, checksum, effective_date, created_at)
  - Unique (hazard_dataset_id, version_label); immutable.
- **hazard_overlay_result**(id UUID PK, tenant_id FK, exposure_version_id FK, hazard_dataset_version_id FK, method, params_json JSONB, created_at, run_id FK→run)
- **location_hazard_attribute**(id UUID PK, location_id FK→location, hazard_overlay_result_id FK, attributes_json JSONB)
  - Index (location_id), (hazard_overlay_result_id), (hazard_overlay_result_id, location_id UNIQUE).

## Analytics
- **rollup_config**(id UUID PK, tenant_id FK, name, dimensions_json JSONB, filters_json JSONB, measures_json JSONB, created_by FK→user, created_at, version INT)
  - Unique (tenant_id, name, version); immutable per version.
- **rollup_result**(id UUID PK, tenant_id FK, exposure_version_id FK, rollup_config_id FK, hazard_overlay_result_ids_json JSONB, storage_uri, checksum, created_at, run_id FK→run)
- **threshold_rule**(id UUID PK, tenant_id FK, name, rule_json JSONB, severity, created_by FK→user, created_at, active BOOLEAN)
  - Versioning handled via new rows; active flag for current usage.
- **breach**(id UUID PK, tenant_id FK, exposure_version_id FK, threshold_rule_id FK, rollup_result_id FK, rollup_key_json JSONB, metric_value NUMERIC, threshold_value NUMERIC, created_at, status ENUM[OPEN,ACKED,RESOLVED], updated_at, updated_by FK→user)
  - Index (tenant_id, exposure_version_id), (tenant_id, status).

## Drift
- **drift_run**(id UUID PK, tenant_id FK, exposure_version_a FK→exposure_version, exposure_version_b FK→exposure_version, config_json JSONB, storage_uri, checksum, created_at, run_id FK→run)
- **drift_detail**(id UUID PK, drift_run_id FK, external_location_id, classification ENUM[NEW,REMOVED,MODIFIED], delta_json JSONB)
  - Index (drift_run_id, classification).

## Governance
- **run**(id UUID PK, tenant_id FK, run_type ENUM[VALIDATION,GEOCODE,OVERLAY,ROLLUP,BREACH_EVAL,DRIFT], input_refs_json JSONB, config_refs_json JSONB, output_refs_json JSONB, code_version, status ENUM[QUEUED,RUNNING,SUCCEEDED,FAILED], created_by FK→user, created_at, started_at, completed_at, artifact_checksums_json JSONB)
- **audit_event**(id UUID PK, tenant_id FK, actor_user_id FK→user, action, entity_type, entity_id, event_json JSONB, created_at)
  - Append-only; index (tenant_id, created_at DESC), (tenant_id, entity_type, entity_id).

## Immutability & Provenance Rules
- exposure_version, mapping_template_version, hazard_dataset_version, run rows are immutable after creation; corrections require new version.
- location rows tied to exposure_version are immutable; geocode/overlay enrichments recorded via overlay_result/run references.
- audit_event never updated or deleted.

## Spatial Considerations
- Use PostGIS geometry/geography for location points and hazard polygons.
- Spatial indexes on hazard geometries and location points to accelerate overlays.
