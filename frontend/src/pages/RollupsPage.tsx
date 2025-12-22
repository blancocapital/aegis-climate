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

export function RollupsPage() {
  const { data: configs = [], refetch } = useRollupConfigs()
  const { data: exposures = [] } = useExposureVersions()
  const createConfig = useCreateRollupConfig()
  const createRollup = useCreateRollup()
  const [configJson, setConfigJson] = useState('{"dimensions": ["country"], "measures": ["tiv_sum"]}')
  const [name, setName] = useState('Country rollup')
  const [selectedConfig, setSelectedConfig] = useState<number | null>(null)
  const [selectedExposure, setSelectedExposure] = useState<number | null>(null)
  const [rollupId, setRollupId] = useState<number | null>(null)
  const rollupQuery = useRollup(rollupId || undefined)
  const [drillKey, setDrillKey] = useState<string>('')
  const drillQuery = useRollupDrilldown(rollupId || undefined, drillKey)

  const configColumns: ColumnDef<any>[] = [
    { header: 'ID', accessorKey: 'id' },
    { header: 'Name', accessorKey: 'name' },
  ]

  const rollupColumns: ColumnDef<any>[] = [
    { header: 'Key', accessorKey: 'rollup_key' },
    { header: 'Metrics', accessorKey: 'metrics', cell: ({ getValue }) => JSON.stringify(getValue()) },
  ]

  const saveConfig = async () => {
    await createConfig.mutateAsync({ name, config_json: JSON.parse(configJson) })
    refetch()
  }

  const startRollup = async () => {
    if (!selectedConfig || !selectedExposure) return
    const res = await createRollup.mutateAsync({ exposure_version_id: selectedExposure, rollup_config_id: selectedConfig })
    setRollupId(res.rollup_result_id)
  }

  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <h2 className="text-lg font-semibold">Rollup configs</h2>
        <div className="grid gap-2 md:grid-cols-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Config name" />
          <Textarea rows={4} value={configJson} onChange={(e) => setConfigJson(e.target.value)} />
        </div>
        <Button onClick={saveConfig}>Save config</Button>
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
          <Button onClick={startRollup}>Start rollup</Button>
        </div>
        {rollupId && (
          <div className="space-y-2">
            <Badge>Result {rollupId}</Badge>
            <DataTable data={rollupQuery.data || []} columns={rollupColumns} />
            <div className="flex items-center gap-2">
              <Input placeholder="Drilldown key" value={drillKey} onChange={(e) => setDrillKey(e.target.value)} />
              <Button onClick={() => drillQuery.refetch()}>Drilldown</Button>
            </div>
            {drillQuery.data && <pre className="rounded bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(drillQuery.data, null, 2)}</pre>}
          </div>
        )}
      </Card>
    </div>
  )
}
