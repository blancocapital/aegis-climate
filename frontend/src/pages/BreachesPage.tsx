import { useState } from 'react'
import { useBreaches, useRunBreachEval, useThresholdRules, useUpdateBreachStatus, useExposureVersions } from '../api/hooks'
import { Card } from '../components/ui/card'
import { Select } from '../components/ui/select'
import { Button } from '../components/ui/button'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'
import { Breach } from '../api/types'
import { formatDate } from '../utils/date'
import { Badge } from '../components/ui/badge'
import { Input } from '../components/ui/input'

export function BreachesPage() {
  const { data: rules = [] } = useThresholdRules()
  const { data: exposures = [] } = useExposureVersions()
  const [ruleId, setRuleId] = useState<number | null>(null)
  const [exposureId, setExposureId] = useState<number | null>(null)
  const [rollupResultId, setRollupResultId] = useState<number | null>(null)
  const { data: breaches = [], refetch } = useBreaches({ exposure_version_id: exposureId, threshold_rule_id: ruleId })
  const update = useUpdateBreachStatus()
  const runEval = useRunBreachEval()

  const columns: ColumnDef<Breach>[] = [
    { header: 'ID', accessorKey: 'id' },
    { header: 'Status', accessorKey: 'status', cell: ({ getValue }) => <Badge>{String(getValue())}</Badge> },
    { header: 'Rule', accessorKey: 'rule_name' },
    { header: 'Rollup Key', accessorKey: 'rollup_key' },
    { header: 'Metric', accessorKey: 'metric_name' },
    { header: 'Value', accessorKey: 'metric_value' },
    { header: 'Threshold', accessorKey: 'threshold_value' },
    { header: 'Last Seen', accessorKey: 'last_seen_at', cell: ({ getValue }) => formatDate(getValue() as string) },
    {
      header: 'Actions',
      cell: ({ row }) => (
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => changeStatus(row.original.id, 'ACKED')}>
            Ack
          </Button>
          <Button variant="ghost" onClick={() => changeStatus(row.original.id, 'RESOLVED')}>
            Resolve
          </Button>
        </div>
      ),
    },
  ]

  const changeStatus = async (id: number, status: string) => {
    await update.mutateAsync({ id, status })
    refetch()
  }

  const triggerEval = async () => {
    if (!ruleId || !rollupResultId) return
    await runEval.mutateAsync({ rollup_result_id: rollupResultId, threshold_rule_ids: [ruleId] })
    refetch()
  }

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-semibold">Breaches</h2>
      <div className="flex flex-wrap gap-2">
        <Select value={ruleId?.toString() || ''} onChange={(e) => setRuleId(Number(e.target.value))}>
          <option value="">Rule</option>
          {rules.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </Select>
        <Select value={exposureId?.toString() || ''} onChange={(e) => setExposureId(Number(e.target.value))}>
          <option value="">Exposure</option>
          {exposures.map((ex) => (
            <option key={ex.id} value={ex.id}>
              {ex.name || ex.id}
            </option>
          ))}
        </Select>
        <Input
          placeholder="Rollup result ID"
          value={rollupResultId?.toString() || ''}
          onChange={(e) => setRollupResultId(e.target.value ? Number(e.target.value) : null)}
        />
        <Button onClick={triggerEval} disabled={!ruleId || !rollupResultId || runEval.isLoading}>
          {runEval.isLoading ? 'Running...' : 'Run evaluation'}
        </Button>
      </div>
      <DataTable data={breaches} columns={columns} />
    </Card>
  )
}
