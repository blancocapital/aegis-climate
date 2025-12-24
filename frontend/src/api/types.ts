import { z } from 'zod'

export const LoginResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
})
export type LoginResponse = z.infer<typeof LoginResponseSchema>

export const UploadResponseSchema = z.object({
  upload_id: z.string(),
  object_uri: z.string(),
})
export type UploadResponse = z.infer<typeof UploadResponseSchema>

export const MappingResponseSchema = z.object({
  mapping_template_id: z.number().optional(),
  mapping_version: z.number().optional(),
  version: z.number().optional(),
  name: z.string().optional(),
})
export type MappingResponse = z.infer<typeof MappingResponseSchema>

const RunSchemaRaw = z.object({
  id: z.number(),
  run_type: z.string(),
  status: z.string(),
  input_refs: z.record(z.any()).nullable().optional(),
  config_refs: z.record(z.any()).nullable().optional(),
  output_refs: z.record(z.any()).nullable().optional(),
  artifact_checksums: z.record(z.any()).nullable().optional(),
  input_refs_json: z.record(z.any()).nullable().optional(),
  config_refs_json: z.record(z.any()).nullable().optional(),
  output_refs_json: z.record(z.any()).nullable().optional(),
  artifact_checksums_json: z.record(z.any()).nullable().optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
})
export const RunSchema = RunSchemaRaw.transform((data) => ({
  ...data,
  input_refs: data.input_refs ?? data.input_refs_json ?? null,
  config_refs: data.config_refs ?? data.config_refs_json ?? null,
  output_refs: data.output_refs ?? data.output_refs_json ?? null,
  artifact_checksums: data.artifact_checksums ?? data.artifact_checksums_json ?? null,
}))
export type Run = z.infer<typeof RunSchema>

export const ValidationResultSchema = z.object({
  id: z.number(),
  summary: z.record(z.any()),
  issues: z.array(z.record(z.any())),
  total_issues: z.number().optional(),
  row_errors_uri: z.string().optional(),
  checksum: z.string().optional(),
  created_at: z.string().optional(),
  mapping_template_id: z.number().nullable().optional(),
  upload_id: z.string().optional(),
})
export type ValidationResult = z.infer<typeof ValidationResultSchema>

export const ExposureVersionSchema = z.object({
  id: z.number(),
  name: z.string().nullable().optional(),
  created_at: z.string().optional(),
  upload_id: z.string().optional(),
  location_count: z.number().optional(),
  tiv_sum: z.number().optional(),
})
export type ExposureVersion = z.infer<typeof ExposureVersionSchema>

export const ExposureLocationSchema = z.object({
  location_id: z.number().optional(),
  external_location_id: z.string().optional(),
  latitude: z.number().nullable().optional(),
  longitude: z.number().nullable().optional(),
  address_line1: z.string().nullable().optional(),
  city: z.string().nullable().optional(),
  state_region: z.string().nullable().optional(),
  postal_code: z.string().nullable().optional(),
  country: z.string().nullable().optional(),
  tiv: z.number().nullable().optional(),
})
export type ExposureLocation = z.infer<typeof ExposureLocationSchema>

export const ExceptionSchema = z.object({
  type: z.string(),
  exception_key: z.string().optional(),
  status: z.string().optional(),
  impact: z.string().optional(),
  recommended_action: z.string().optional(),
  location_id: z.number().optional(),
  external_location_id: z.string().optional(),
  severity: z.string().optional(),
  message: z.string().optional(),
  field: z.string().optional(),
  code: z.string().optional(),
  row_number: z.number().optional(),
  quality_tier: z.string().optional(),
  reasons: z.array(z.string()).optional(),
  geocode_confidence: z.number().optional(),
})
export type ExposureException = z.infer<typeof ExceptionSchema>

export const HazardDatasetSchema = z.object({
  id: z.number(),
  name: z.string(),
  peril: z.string().optional(),
  vendor: z.string().nullable().optional(),
  coverage_geo: z.string().nullable().optional(),
  license_ref: z.string().nullable().optional(),
  created_at: z.string().optional(),
})
export type HazardDataset = z.infer<typeof HazardDatasetSchema>

export const HazardDatasetVersionSchema = z.object({
  id: z.number(),
  version_label: z.string().optional(),
  checksum: z.string().optional(),
  created_at: z.string().optional(),
  effective_date: z.string().nullable().optional(),
})
export type HazardDatasetVersion = z.infer<typeof HazardDatasetVersionSchema>

export const HazardOverlaySchema = z.object({
  overlay_result_id: z.number(),
  run_id: z.number().optional(),
})
export type HazardOverlayCreateResponse = z.infer<typeof HazardOverlaySchema>

export const OverlayStatusSchema = z.object({
  overlay_result_id: z.number(),
  status: z.string(),
  run_id: z.number().optional(),
})
export type OverlayStatus = z.infer<typeof OverlayStatusSchema>

export const RollupConfigSchema = z.object({
  id: z.number(),
  name: z.string(),
  created_at: z.string().optional(),
  version: z.number().optional(),
  dimensions_json: z.array(z.any()).optional(),
  filters_json: z.record(z.any()).nullable().optional(),
  measures_json: z.array(z.any()).optional(),
})
export type RollupConfig = z.infer<typeof RollupConfigSchema>

export const RollupRowSchema = z.object({
  rollup_key: z.string().optional(),
  rollup_key_json: z.record(z.any()).optional(),
  metrics: z.record(z.any()),
})
export type RollupRow = z.infer<typeof RollupRowSchema>

export const ThresholdRuleSchema = z.object({
  id: z.number(),
  name: z.string(),
  severity: z.string(),
  active: z.boolean().optional(),
  rule_json: z.any(),
})
export type ThresholdRule = z.infer<typeof ThresholdRuleSchema>

export const BreachSchema = z.object({
  id: z.number(),
  rule_id: z.number().optional(),
  rule_name: z.string().optional(),
  exposure_version_id: z.number().optional(),
  rollup_result_id: z.number().optional(),
  status: z.string(),
  rollup_key: z.string().optional(),
  metric_name: z.string().optional(),
  metric_value: z.number().optional(),
  threshold_value: z.number().optional(),
  first_seen_at: z.string().optional(),
  last_seen_at: z.string().optional(),
})
export type Breach = z.infer<typeof BreachSchema>

export const UWRuleSchema = z.object({
  id: z.number(),
  name: z.string(),
  category: z.string(),
  severity: z.string(),
  target: z.string(),
  active: z.boolean().optional(),
  rule_json: z.any(),
  created_at: z.string().optional(),
})
export type UWRule = z.infer<typeof UWRuleSchema>

export const UWFindingSchema = z.object({
  id: z.number(),
  status: z.string(),
  disposition: z.string(),
  uw_rule_id: z.number(),
  rule_name: z.string().optional(),
  rule_category: z.string().optional(),
  rule_severity: z.string().optional(),
  rule_target: z.string().optional(),
  exposure_version_id: z.number().optional(),
  location_id: z.number().nullable().optional(),
  external_location_id: z.string().nullable().optional(),
  state_region: z.string().nullable().optional(),
  lob: z.string().nullable().optional(),
  product_code: z.string().nullable().optional(),
  rollup_result_id: z.number().nullable().optional(),
  rollup_key_hash: z.string().nullable().optional(),
  explanation: z.any().optional(),
  first_seen_at: z.string().optional(),
  last_seen_at: z.string().optional(),
  resolved_at: z.string().nullable().optional(),
})
export type UWFinding = z.infer<typeof UWFindingSchema>

export const UWNoteSchema = z.object({
  id: z.number(),
  entity_type: z.string(),
  entity_id: z.string(),
  note_text: z.string(),
  created_at: z.string().optional(),
})
export type UWNote = z.infer<typeof UWNoteSchema>

export const UWDecisionSchema = z.object({
  id: z.number(),
  exposure_version_id: z.number(),
  decision: z.string(),
  conditions_json: z.array(z.string()).optional(),
  rationale_text: z.string(),
  created_at: z.string().optional(),
})
export type UWDecision = z.infer<typeof UWDecisionSchema>

export const UWSummarySchema = z.object({
  exposure_version: z.record(z.any()),
  data_quality: z.record(z.any()),
  hazard_mix: z.record(z.any()),
  concentration: z.record(z.any()),
  controls: z.record(z.any()),
  latest_runs: z.array(z.record(z.any())).optional(),
}).passthrough()
export type UWSummary = z.infer<typeof UWSummarySchema>

export const AuditEventSchema = z.object({
  action: z.string(),
  user_id: z.string().nullable().optional(),
  metadata: z.record(z.any()).nullable().optional(),
  created_at: z.string().optional(),
})
export type AuditEvent = z.infer<typeof AuditEventSchema>

const UnderwritingDecisionSchema = z.object({
  decision: z.string(),
  confidence: z.number(),
  reason_codes: z.array(z.string()).optional(),
  reasons: z.array(z.string()).optional(),
  mitigation_recommendations: z.array(z.record(z.any())).optional(),
}).passthrough()

const ExplainabilityDriverSchema = z.object({
  peril: z.string(),
  contribution_pct: z.number(),
}).passthrough()

const ExplainabilitySchema = z.object({
  narrative: z.string(),
  drivers: z.array(ExplainabilityDriverSchema),
}).passthrough()

const QualitySchema = z.object({
  enrichment_status: z.string().optional(),
  data_quality: z.object({ enrichment_status: z.string().optional() }).passthrough().optional(),
}).passthrough()

export const UnderwritingPacketSuccessSchema = z.object({
  property: z.record(z.any()).optional(),
  hazards: z.record(z.any()).optional(),
  resilience: z.record(z.any()).optional(),
  provenance: z.record(z.any()).optional(),
  quality: QualitySchema.optional(),
  decision: UnderwritingDecisionSchema.nullable().optional(),
  explainability: ExplainabilitySchema,
}).passthrough()
export type UnderwritingPacketSuccess = z.infer<typeof UnderwritingPacketSuccessSchema>

export const UnderwritingPacketQueuedSchema = z.object({
  status: z.literal('ENRICHMENT_QUEUED'),
  run_id: z.number(),
  message: z.string().optional(),
  address_fingerprint: z.string().optional(),
}).passthrough()
export type UnderwritingPacketQueued = z.infer<typeof UnderwritingPacketQueuedSchema>

export const UnderwritingPacketResponseSchema = z.union([
  UnderwritingPacketSuccessSchema,
  UnderwritingPacketQueuedSchema,
])
export type UnderwritingPacketResponse = z.infer<typeof UnderwritingPacketResponseSchema>
