import { useState } from 'react'
import { useCreateOverlay, useExposureVersions, useHazardDatasetVersions, useHazardDatasets, useOverlayStatus, useOverlaySummary } from '../api/hooks'
import { Card } from '../components/ui/card'
import { Select } from '../components/ui/select'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'

export function OverlaysPage() {
  const { data: exposures = [] } = useExposureVersions()
  const { data: datasets = [] } = useHazardDatasets()
  const [datasetId, setDatasetId] = useState<number | null>(null)
  const versions = useHazardDatasetVersions(datasetId || undefined)
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null)
  const [overlayId, setOverlayId] = useState<number | null>(null)
  const statusQuery = useOverlayStatus(overlayId || undefined)
  const summaryQuery = useOverlaySummary(overlayId || undefined)
  const createOverlay = useCreateOverlay()
  const [exposureId, setExposureId] = useState<number | null>(null)

  const startOverlay = async () => {
    if (!exposureId || !selectedVersion) return
    const res = await createOverlay.mutateAsync({ exposure_version_id: exposureId, hazard_dataset_version_ids: [selectedVersion] })
    setOverlayId(res.overlay_result_id)
  }

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-semibold">Hazard overlays</h2>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <Select value={exposureId?.toString() || ''} onChange={(e) => setExposureId(Number(e.target.value))}>
          <option value="">Select exposure version</option>
          {exposures.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name || e.id}
            </option>
          ))}
        </Select>
        <Select value={datasetId?.toString() || ''} onChange={(e) => setDatasetId(Number(e.target.value))}>
          <option value="">Select hazard dataset</option>
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </Select>
        <Select value={selectedVersion?.toString() || ''} onChange={(e) => setSelectedVersion(Number(e.target.value))}>
          <option value="">Select version</option>
          {versions.data?.map((v) => (
            <option key={v.id} value={v.id}>
              {v.version_label ? `${v.version_label} (#${v.id})` : `Version ${v.id}`}
            </option>
          ))}
        </Select>
      </div>
      <Button onClick={startOverlay} disabled={!exposureId || !selectedVersion || createOverlay.isLoading}>
        {createOverlay.isLoading ? 'Starting...' : 'Start overlay'}
      </Button>
      {overlayId && (
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <Badge>{statusQuery.data?.status || 'PENDING'}</Badge>
            <span>Overlay result {overlayId}</span>
          </div>
          {summaryQuery.data ? (
            <pre className="rounded bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(summaryQuery.data, null, 2)}</pre>
          ) : (
            <p className="text-slate-600">No summary yet.</p>
          )}
        </div>
      )}
    </Card>
  )
}
