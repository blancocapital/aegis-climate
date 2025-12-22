import { useState } from 'react'
import { useExposureExceptions, useExposureVersions } from '../api/hooks'
import { Card } from '../components/ui/card'
import { Select } from '../components/ui/select'
import { Badge } from '../components/ui/badge'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'

export function ExceptionsPage() {
  const { data: versions = [] } = useExposureVersions()
  const [selected, setSelected] = useState<string>('')
  const { data: exceptions = [], isLoading } = useExposureExceptions(selected)

  const rows = exceptions.map((ex) => {
    const details = [
      ex.row_number ? `Row ${ex.row_number}` : null,
      ex.field ? `Field ${ex.field}` : null,
      ex.geocode_confidence !== undefined ? `Geo conf ${ex.geocode_confidence}` : null,
      ex.reasons && ex.reasons.length ? `Reasons: ${ex.reasons.join(', ')}` : null,
    ]
      .filter(Boolean)
      .join(' · ')
    return {
      type: ex.type,
      external_location_id: ex.external_location_id,
      severity: ex.severity || (ex.type === 'VALIDATION_ISSUE' ? 'ERROR' : undefined),
      message: ex.message || ex.code || (ex.quality_tier ? `Quality tier ${ex.quality_tier}` : undefined),
      details: details || '-',
    }
  })

  const columns: ColumnDef<(typeof rows)[number]>[] = [
    { header: 'Type', accessorKey: 'type', cell: ({ getValue }) => <Badge>{String(getValue())}</Badge> },
    { header: 'External ID', accessorKey: 'external_location_id' },
    { header: 'Severity', accessorKey: 'severity' },
    { header: 'Message', accessorKey: 'message' },
    { header: 'Details', accessorKey: 'details' },
  ]

  return (
    <Card className="space-y-3">
      <div className="flex items-center gap-3">
        <div>
          <h2 className="text-lg font-semibold">Exceptions</h2>
          <p className="text-sm text-slate-600">Filter by exposure version.</p>
        </div>
        <Select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">Select exposure version</option>
          {versions.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name || v.id}
            </option>
          ))}
        </Select>
      </div>
      {selected ? (
        isLoading ? (
          <p>Loading...</p>
        ) : rows.length ? (
          <DataTable data={rows} columns={columns} />
        ) : (
          <p className="text-sm text-slate-600">No exceptions for this version.</p>
        )
      ) : (
        <p className="text-sm text-slate-600">Choose a version to view exceptions.</p>
      )}
    </Card>
  )
}
