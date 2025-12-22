import { useState } from 'react'
import { useCreateRollup, useCreateRollupConfig, useExposureVersions, useRollup, useRollupConfigs, useRollupDrilldown } from '../api/hooks'
import { Card } from '../components/ui/card'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'
import { Input } from '../components/ui/input'
import { Button } from '../components/ui/button'
import { Textarea } from '../components/ui/textarea'
import { Select } from '../components/ui/select'
import { Badge } from '../components/ui/badge'
import { toast } from 'sonner'

export function RollupsPage() {
  const { data: configs = [], refetch } = useRollupConfigs()
  const { data: exposures = [] } = useExposureVersions()
  const createConfig = useCreateRollupConfig()
  const createRollup = useCreateRollup()
  const [configJson, setConfigJson] = useState('{"dimensions": ["country"], "measures": [{"name": "tiv_sum", "op": "sum", "field": "tiv"}]}')
  const [name, setName] = useState('Country rollup')
  const [selectedConfig, setSelectedConfig] = useState<number | null>(null)
  const [selectedExposure, setSelectedExposure] = useState<number | null>(null)
  const [rollupId, setRollupId] = useState<number | null>(null)
  const [overlayIds, setOverlayIds] = useState<string>('')
  const rollupQuery = useRollup(rollupId || undefined)
  const [drillKeyJson, setDrillKeyJson] = useState<string>('{}')
  const [drillKeyB64, setDrillKeyB64] = useState<string>('')
  const drillQuery = useRollupDrilldown(rollupId || undefined, drillKeyB64)

  const configColumns: ColumnDef<any>[] = [
    { header: 'ID', accessorKey: 'id' },
    { header: 'Name', accessorKey: 'name' },
  ]

  const rollupColumns: ColumnDef<any>[] = [
    { header: 'Key', accessorKey: 'rollup_key' },
    { header: 'Metrics', accessorKey: 'metrics', cell: ({ getValue }) => JSON.stringify(getValue()) },
  ]

  const saveConfig = async () => {
    let parsed: any
    try {
      parsed = JSON.parse(configJson)
    } catch (err) {
      toast.error('Config JSON is invalid')
      return
    }
    if (!Array.isArray(parsed.dimensions) || !Array.isArray(parsed.measures)) {
      toast.error('Config must include dimensions and measures arrays')
      return
    }
    await createConfig.mutateAsync({
      name,
      dimensions_json: parsed.dimensions,
      measures_json: parsed.measures,
      filters_json: parsed.filters || undefined,
    })
    refetch()
  }

  const startRollup = async () => {
    if (!selectedConfig || !selectedExposure) return
    const parsedOverlayIds = overlayIds
      .split(',')
      .map((id) => id.trim())
      .filter(Boolean)
      .map((id) => Number(id))
      .filter((id) => !Number.isNaN(id))
    const res = await createRollup.mutateAsync({
      exposure_version_id: selectedExposure,
      rollup_config_id: selectedConfig,
      hazard_overlay_result_ids: parsedOverlayIds,
    })
    setRollupId(res.rollup_result_id)
  }

  const requestDrilldown = () => {
    try {
      const parsed = JSON.parse(drillKeyJson)
      const raw = JSON.stringify(parsed)
      const encoded = btoa(raw).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
      setDrillKeyB64(encoded)
    } catch (err) {
      toast.error('Drilldown key must be valid JSON')
    }
  }

  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <h2 className="text-lg font-semibold">Rollup configs</h2>
        <div className="grid gap-2 md:grid-cols-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Config name" />
          <Textarea rows={4} value={configJson} onChange={(e) => setConfigJson(e.target.value)} />
        </div>
        <Button onClick={saveConfig} disabled={createConfig.isLoading}>
          {createConfig.isLoading ? 'Saving...' : 'Save config'}
        </Button>
        <DataTable data={configs} columns={configColumns} />
      </Card>
      <Card className="space-y-3">
        <h3 className="text-lg font-semibold">Run rollup</h3>
        <div className="grid gap-3 md:grid-cols-3">
          <Select value={selectedExposure?.toString() || ''} onChange={(e) => setSelectedExposure(Number(e.target.value))}>
            <option value="">Exposure</option>
            {exposures.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name || e.id}
              </option>
            ))}
          </Select>
          <Select value={selectedConfig?.toString() || ''} onChange={(e) => setSelectedConfig(Number(e.target.value))}>
            <option value="">Config</option>
            {configs.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <Input
            placeholder="Overlay result IDs (comma separated)"
            value={overlayIds}
            onChange={(e) => setOverlayIds(e.target.value)}
          />
          <Button onClick={startRollup} disabled={!selectedConfig || !selectedExposure || createRollup.isLoading}>
            {createRollup.isLoading ? 'Starting...' : 'Start rollup'}
          </Button>
        </div>
        {rollupId && (
          <div className="space-y-2">
            <Badge>Result {rollupId}</Badge>
            <DataTable data={rollupQuery.data || []} columns={rollupColumns} />
            <div className="flex items-center gap-2">
              <Input placeholder="Drilldown key JSON" value={drillKeyJson} onChange={(e) => setDrillKeyJson(e.target.value)} />
              <Button onClick={requestDrilldown}>Drilldown</Button>
            </div>
            {drillQuery.data && <pre className="rounded bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(drillQuery.data, null, 2)}</pre>}
          </div>
        )}
      </Card>
    </div>
  )
}
