import { useState } from 'react'
import { useCreateUWNote, useExposureExceptions, useExposureVersions, useUpdateExceptionStatus, useUWNotes } from '../api/hooks'
import { Card } from '../components/ui/card'
import { Select } from '../components/ui/select'
import { Badge } from '../components/ui/badge'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'
import { Button } from '../components/ui/button'
import { Textarea } from '../components/ui/textarea'
import { formatDate } from '../utils/date'

export function ExceptionsPage() {
  const { data: versions = [] } = useExposureVersions()
  const [selected, setSelected] = useState<string>('')
  const exceptionsQuery = useExposureExceptions(selected)
  const { data: exceptions = [], isLoading } = exceptionsQuery
  const updateException = useUpdateExceptionStatus()
  const createNote = useCreateUWNote()
  const [selectedException, setSelectedException] = useState<any | null>(null)
  const notesQuery = useUWNotes('EXCEPTION', selectedException?.exception_key)
  const [noteText, setNoteText] = useState('')

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
      exception_key: ex.exception_key,
      status: ex.status || 'OPEN',
      impact: ex.impact,
      recommended_action: ex.recommended_action,
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
    { header: 'Status', accessorKey: 'status' },
    { header: 'Details', accessorKey: 'details' },
    {
      header: 'Action',
      accessorKey: 'exception_key',
      cell: ({ row }) => (
        <Button variant="ghost" onClick={() => setSelectedException(row.original)}>
          Review
        </Button>
      ),
    },
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
          <div className="grid gap-4 lg:grid-cols-[2fr,1fr]">
            <DataTable data={rows} columns={columns} />
            <Card className="space-y-3 p-3">
              <h3 className="text-lg font-semibold">Exception details</h3>
              {selectedException ? (
                <>
                  <div className="space-y-1 text-sm">
                    <div className="flex items-center gap-2">
                      <Badge>{selectedException.status}</Badge>
                      <Badge className="bg-slate-100 text-slate-700">{selectedException.type}</Badge>
                    </div>
                    <div>{selectedException.message}</div>
                    <div className="text-slate-600">{selectedException.details}</div>
                    <div className="text-slate-600">Impact: {selectedException.impact || '-'}</div>
                    <div className="text-slate-600">Action: {selectedException.recommended_action || '-'}</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="ghost"
                      onClick={async () => {
                        if (!selectedException.exception_key) return
                        await updateException.mutateAsync({ exception_key: selectedException.exception_key, status: 'ACKED' })
                        setSelectedException({ ...selectedException, status: 'ACKED' })
                        exceptionsQuery.refetch()
                      }}
                    >
                      Ack
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={async () => {
                        if (!selectedException.exception_key) return
                        await updateException.mutateAsync({ exception_key: selectedException.exception_key, status: 'RESOLVED' })
                        setSelectedException({ ...selectedException, status: 'RESOLVED' })
                        exceptionsQuery.refetch()
                      }}
                    >
                      Resolve
                    </Button>
                  </div>
                  <div className="space-y-2">
                    <div className="text-sm font-medium">Notes</div>
                    {(notesQuery.data ?? []).map((note) => (
                      <div key={note.id} className="rounded-md border border-slate-200 p-2 text-sm">
                        <div className="text-xs text-slate-500">{formatDate(note.created_at)}</div>
                        <div>{note.note_text}</div>
                      </div>
                    ))}
                    <Textarea placeholder="Add a note" value={noteText} onChange={(e) => setNoteText(e.target.value)} />
                    <Button
                      onClick={async () => {
                        if (!noteText.trim() || !selectedException.exception_key) return
                        await createNote.mutateAsync({
                          entity_type: 'EXCEPTION',
                          entity_id: selectedException.exception_key,
                          note_text: noteText.trim(),
                        })
                        setNoteText('')
                        notesQuery.refetch()
                      }}
                      disabled={!noteText.trim()}
                    >
                      Add note
                    </Button>
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-600">Select an exception to view details.</p>
              )}
            </Card>
          </div>
        ) : (
          <p className="text-sm text-slate-600">No exceptions for this version.</p>
        )
      ) : (
        <p className="text-sm text-slate-600">Choose a version to view exceptions.</p>
      )}
    </Card>
  )
}
