import { useMutation, useQuery } from '@tanstack/react-query'
import { apiRequest } from './client'
import {
  AuditEventSchema,
  BreachSchema,
  ExceptionSchema,
  ExposureLocationSchema,
  ExposureVersionSchema,
  HazardDatasetSchema,
  HazardDatasetVersionSchema,
  HazardOverlaySchema,
  LoginResponseSchema,
  MappingResponseSchema,
  OverlayStatusSchema,
  RollupConfigSchema,
  RollupRowSchema,
  RunSchema,
  ThresholdRuleSchema,
  UploadResponseSchema,
} from './types'

const pollingStatuses = ['QUEUED', 'RUNNING']

export function useLogin() {
  return useMutation({
    mutationFn: (payload: { email: string; password: string; tenant_id: string }) =>
      apiRequest({ method: 'POST', path: '/auth/login', body: payload }).then((r) => LoginResponseSchema.parse(r)),
  })
}

export function useUploadFile() {
  return useMutation({
    mutationFn: (payload: { file: File; idempotencyKey?: string }) => {
      const data = new FormData()
      data.append('file', payload.file)
      return apiRequest({
        method: 'POST',
        path: '/uploads',
        body: data,
        isMultipart: true,
        headers: payload.idempotencyKey ? { 'Idempotency-Key': payload.idempotencyKey } : undefined,
      }).then((res) => UploadResponseSchema.parse(res))
    },
  })
}

export function useCreateMapping(uploadId?: string) {
  return useMutation({
    mutationFn: (payload: { name: string; mapping_json: Record<string, any> }) =>
      apiRequest({ method: 'POST', path: `/uploads/${uploadId}/mapping`, body: payload }).then((res) =>
        MappingResponseSchema.parse(res)
      ),
  })
}

export function useValidateUpload(uploadId?: string) {
  return useMutation({
    mutationFn: () => apiRequest<{ run_id: number }>({ method: 'POST', path: `/uploads/${uploadId}/validate` }),
  })
}

export function useCommitUpload(uploadId?: string) {
  return useMutation({
    mutationFn: (payload: { name?: string }) => apiRequest<{ run_id: number }>({ method: 'POST', path: `/uploads/${uploadId}/commit`, body: payload }),
  })
}

export function useRun(runId?: number, enabled = true) {
  return useQuery({
    queryKey: ['run', runId],
    queryFn: () => apiRequest({ path: `/runs/${runId}` }).then((res) => RunSchema.parse(res)),
    enabled: Boolean(runId) && enabled,
    refetchInterval: (data) =>
      data && pollingStatuses.includes((data as any).status)
        ? 1500
        : false,
  })
}

export function useRuns(params?: { status?: string }) {
  return useQuery({
    queryKey: ['runs', params],
    queryFn: () => apiRequest({ path: '/runs', params }).then((res) => RunSchema.array().parse(res)),
  })
}

export function useExposureVersions() {
  return useQuery({
    queryKey: ['exposure-versions'],
    queryFn: () => apiRequest({ path: '/exposure-versions' }).then((res) => ExposureVersionSchema.array().parse(res)),
  })
}

export function useExposureVersion(id?: string | number) {
  return useQuery({
    queryKey: ['exposure-version', id],
    queryFn: () => apiRequest({ path: `/exposure-versions/${id}` }).then((res) => ExposureVersionSchema.parse(res)),
    enabled: Boolean(id),
  })
}

export function useExposureLocations(id?: string | number, params?: Record<string, any>) {
  return useQuery({
    queryKey: ['exposure-locations', id, params],
    queryFn: () => apiRequest({ path: `/exposure-versions/${id}/locations`, params }).then((res) => ExposureLocationSchema.array().parse(res)),
    enabled: Boolean(id),
  })
}

export function useExposureExceptions(id?: string | number) {
  return useQuery({
    queryKey: ['exposure-exceptions', id],
    queryFn: () => apiRequest({ path: `/exposure-versions/${id}/exceptions` }).then((res) => ExceptionSchema.array().parse(res)),
    enabled: Boolean(id),
  })
}

export function useHazardDatasets() {
  return useQuery({
    queryKey: ['hazard-datasets'],
    queryFn: () => apiRequest({ path: '/hazard-datasets' }).then((res) => HazardDatasetSchema.array().parse(res)),
  })
}

export function useHazardDatasetVersions(id?: number) {
  return useQuery({
    queryKey: ['hazard-dataset-versions', id],
    queryFn: () => apiRequest({ path: `/hazard-datasets/${id}/versions` }).then((res) => HazardDatasetVersionSchema.array().parse(res)),
    enabled: Boolean(id),
  })
}

export function useCreateHazardDataset() {
  return useMutation({
    mutationFn: (payload: { name: string; description?: string }) =>
      apiRequest({ method: 'POST', path: '/hazard-datasets', body: payload }).then((res) => HazardDatasetSchema.parse(res)),
  })
}

export function useUploadHazardVersion(datasetId?: number) {
  return useMutation({
    mutationFn: (payload: { file: File }) => {
      const data = new FormData()
      data.append('file', payload.file)
      return apiRequest({
        method: 'POST',
        path: `/hazard-datasets/${datasetId}/versions`,
        body: data,
        isMultipart: true,
      }).then((res) => HazardDatasetVersionSchema.parse(res))
    },
  })
}

export function useCreateOverlay() {
  return useMutation({
    mutationFn: (payload: { exposure_version_id: number; hazard_dataset_version_ids: number[] }) =>
      apiRequest({ method: 'POST', path: '/hazard-overlays', body: payload }).then((res) => HazardOverlaySchema.parse(res)),
  })
}

export function useOverlayStatus(id?: number) {
  return useQuery({
    queryKey: ['overlay-status', id],
    queryFn: () => apiRequest({ path: `/hazard-overlays/${id}/status` }).then((res) => OverlayStatusSchema.parse(res)),
    enabled: Boolean(id),
    refetchInterval: (data) =>
      data && pollingStatuses.includes((data as any).status)
        ? 1500
        : false,
  })
}

export function useOverlaySummary(id?: number) {
  return useQuery({
    queryKey: ['overlay-summary', id],
    queryFn: () => apiRequest({ path: `/hazard-overlays/${id}/summary` }),
    enabled: Boolean(id),
  })
}

export function useRollupConfigs() {
  return useQuery({
    queryKey: ['rollup-configs'],
    queryFn: () => apiRequest({ path: '/rollup-configs' }).then((res) => RollupConfigSchema.array().parse(res)),
  })
}

export function useCreateRollupConfig() {
  return useMutation({
    mutationFn: (payload: { name: string; config_json: any }) =>
      apiRequest({ method: 'POST', path: '/rollup-configs', body: payload }).then((res) => RollupConfigSchema.parse(res)),
  })
}

export function useCreateRollup() {
  return useMutation({
    mutationFn: (payload: { exposure_version_id: number; rollup_config_id: number; overlay_result_ids?: number[] }) =>
      apiRequest({ method: 'POST', path: '/rollups', body: payload }).then((res) => ({ rollup_result_id: res.id, run_id: res.run_id })),
  })
}

export function useRollup(id?: number) {
  return useQuery({
    queryKey: ['rollup', id],
    queryFn: () => apiRequest({ path: `/rollups/${id}` }).then((res) => RollupRowSchema.array().parse(res)),
    enabled: Boolean(id),
  })
}

export function useRollupDrilldown(id?: number, key?: string) {
  return useQuery({
    queryKey: ['rollup-drilldown', id, key],
    queryFn: () => apiRequest({ path: `/rollups/${id}/drilldown`, params: { rollup_key: key } }),
    enabled: Boolean(id && key),
  })
}

export function useThresholdRules() {
  return useQuery({
    queryKey: ['threshold-rules'],
    queryFn: () => apiRequest({ path: '/threshold-rules' }).then((res) => ThresholdRuleSchema.array().parse(res)),
  })
}

export function useCreateThresholdRule() {
  return useMutation({
    mutationFn: (payload: { name: string; severity: string; rule_json: any; active?: boolean }) =>
      apiRequest({ method: 'POST', path: '/threshold-rules', body: payload }).then((res) => ThresholdRuleSchema.parse(res)),
  })
}

export function useBreaches(params?: Record<string, any>) {
  return useQuery({
    queryKey: ['breaches', params],
    queryFn: () => apiRequest({ path: '/breaches', params }).then((res) => BreachSchema.array().parse(res)),
  })
}

export function useRunBreachEval() {
  return useMutation({
    mutationFn: (payload: { rollup_result_id: number; threshold_rule_ids?: number[] }) =>
      apiRequest({ method: 'POST', path: '/breaches/run', body: payload }),
  })
}

export function useUpdateBreachStatus() {
  return useMutation({
    mutationFn: (payload: { id: number; status: string }) =>
      apiRequest({ method: 'PATCH', path: `/breaches/${payload.id}`, body: { status: payload.status } }),
  })
}

export function useAuditEvents(params?: Record<string, any>) {
  return useQuery({
    queryKey: ['audit-events', params],
    queryFn: () => apiRequest({ path: '/audit-events', params }).then((res) => AuditEventSchema.array().parse(res)),
  })
}
