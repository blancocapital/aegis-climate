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
})
export type MappingResponse = z.infer<typeof MappingResponseSchema>

export const RunSchema = z.object({
  id: z.number(),
  run_type: z.string(),
  status: z.string(),
  input_refs_json: z.record(z.any()).nullable().optional(),
  config_refs_json: z.record(z.any()).nullable().optional(),
  output_refs_json: z.record(z.any()).nullable().optional(),
  artifact_checksums_json: z.record(z.any()).nullable().optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
})
export type Run = z.infer<typeof RunSchema>

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
  id: z.string().or(z.number()),
  external_location_id: z.string().optional(),
  latitude: z.number().nullable().optional(),
  longitude: z.number().nullable().optional(),
  address: z.string().nullable().optional(),
  city: z.string().nullable().optional(),
  state: z.string().nullable().optional(),
  country: z.string().nullable().optional(),
  tiv: z.number().nullable().optional(),
})
export type ExposureLocation = z.infer<typeof ExposureLocationSchema>

export const ExceptionSchema = z.object({
  id: z.number(),
  type: z.string(),
  severity: z.string().optional(),
  message: z.string().optional(),
  external_location_id: z.string().optional(),
})
export type ExposureException = z.infer<typeof ExceptionSchema>

export const HazardDatasetSchema = z.object({
  id: z.number(),
  name: z.string(),
  description: z.string().nullable().optional(),
  created_at: z.string().optional(),
})
export type HazardDataset = z.infer<typeof HazardDatasetSchema>

export const HazardDatasetVersionSchema = z.object({
  id: z.number(),
  checksum: z.string().optional(),
  created_at: z.string().optional(),
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
  config_json: z.any().optional(),
})
export type RollupConfig = z.infer<typeof RollupConfigSchema>

export const RollupRowSchema = z.object({
  rollup_key: z.string(),
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
  exposure_version_id: z.number().optional(),
  rollup_result_id: z.number().optional(),
  rule_id: z.number().optional(),
  rule_name: z.string().optional(),
  status: z.string(),
  last_seen_at: z.string().optional(),
  rollup_key: z.string().optional(),
})
export type Breach = z.infer<typeof BreachSchema>

export const AuditEventSchema = z.object({
  id: z.number(),
  action: z.string(),
  metadata_json: z.record(z.any()).nullable().optional(),
  created_at: z.string().optional(),
})
export type AuditEvent = z.infer<typeof AuditEventSchema>
