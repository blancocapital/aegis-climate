import { useState } from 'react'
import { useRuns, useRun } from '../api/hooks'
import { Card } from '../components/ui/card'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'
import { Run } from '../api/types'
import { formatDate } from '../utils/date'
import { Badge } from '../components/ui/badge'
import { Input } from '../components/ui/input'

export function RunsPage() {
  const [runId, setRunId] = useState<number | null>(null)
  const { data: runs = [] } = useRuns()
  const runQuery = useRun(runId || undefined, Boolean(runId))

  const columns: ColumnDef<Run>[] = [
    { header: 'ID', accessorKey: 'id' },
    { header: 'Type', accessorKey: 'run_type' },
    { header: 'Status', accessorKey: 'status', cell: ({ getValue }) => <Badge>{String(getValue())}</Badge> },
    { header: 'Created', accessorKey: 'created_at', cell: ({ getValue }) => formatDate(getValue() as string) },
  ]

  return (
    <div className="space-y-4">
      <Card className="space-y-2">
        <h2 className="text-lg font-semibold">Runs</h2>
        <DataTable data={runs} columns={columns} />
      </Card>
      <Card className="space-y-2">
        <div className="flex items-center gap-2">
          <Input
            placeholder="Run ID"
            onChange={(e) => {
              const value = e.target.value.trim()
              if (!value) {
                setRunId(null)
                return
              }
              const parsed = Number(value)
              setRunId(Number.isNaN(parsed) ? null : parsed)
            }}
          />
        </div>
        {runQuery.data ? (
          <pre className="rounded bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(runQuery.data, null, 2)}</pre>
        ) : (
          <p className="text-sm text-slate-600">Enter a run id to inspect.</p>
        )}
      </Card>
    </div>
  )
}
