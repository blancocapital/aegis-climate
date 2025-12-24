import { useMemo, useState } from 'react'
import { Card } from '../components/ui/card'
import { Select } from '../components/ui/select'
import { Input } from '../components/ui/input'
import { Button } from '../components/ui/button'
import { Textarea } from '../components/ui/textarea'
import { Badge } from '../components/ui/badge'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'
import {
  useCreateUWNote,
  useExposureVersions,
  useUWFindingList,
  useUWNotes,
  useUpdateUWFinding,
} from '../api/hooks'
import { UWFinding } from '../api/types'
import { formatDate } from '../utils/date'

const statusOptions = ['OPEN', 'ACKED', 'RESOLVED']
const dispositionOptions = ['NONE', 'REFER', 'CONDITION', 'DECLINE']
const severityOptions = ['INFO', 'WARN', 'CRITICAL']
const targetOptions = ['LOCATION', 'ROLLUP']

export function UnderwritingFindingsPage() {
  const { data: exposures = [] } = useExposureVersions()
  const [selectedExposure, setSelectedExposure] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [dispositionFilter, setDispositionFilter] = useState<string>('')
  const [severityFilter, setSeverityFilter] = useState<string>('')
  const [targetFilter, setTargetFilter] = useState<string>('')
  const [hazardBandFilter, setHazardBandFilter] = useState<string>('')
  const [stateFilter, setStateFilter] = useState<string>('')
  const [lobFilter, setLobFilter] = useState<string>('')
  const [searchExternal, setSearchExternal] = useState<string>('')

  const findingsQuery = useUWFindingList({
    exposure_version_id: selectedExposure ?? undefined,
    status_filter: statusFilter || undefined,
    disposition: dispositionFilter || undefined,
    severity: severityFilter || undefined,
    target: targetFilter || undefined,
  })
  const updateFinding = useUpdateUWFinding()
  const createNote = useCreateUWNote()
  const [selectedFinding, setSelectedFinding] = useState<UWFinding | null>(null)
  const notesQuery = useUWNotes('FINDING', selectedFinding ? String(selectedFinding.id) : undefined)
  const [noteText, setNoteText] = useState('')

  const filteredFindings = useMemo(() => {
    const list = findingsQuery.data ?? []
    return list.filter((finding) => {
      if (hazardBandFilter) {
        const hazardBands = finding.explanation?.context?.hazard_band || []
        const bandMatch = Array.isArray(hazardBands)
          ? hazardBands.includes(hazardBandFilter)
          : hazardBands === hazardBandFilter
        if (!bandMatch) return false
      }
      if (stateFilter && finding.state_region !== stateFilter) return false
      if (lobFilter && finding.lob !== lobFilter && finding.product_code !== lobFilter) return false
      if (searchExternal && !String(finding.external_location_id || '').includes(searchExternal)) return false
      return true
    })
  }, [findingsQuery.data, hazardBandFilter, stateFilter, lobFilter, searchExternal])

  const columns: ColumnDef<UWFinding>[] = [
    { header: 'Status', accessorKey: 'status' },
    { header: 'Disposition', accessorKey: 'disposition' },
    { header: 'Severity', accessorKey: 'rule_severity' },
    { header: 'Rule', accessorKey: 'rule_name' },
    { header: 'Target', accessorKey: 'rule_target' },
    { header: 'Location', accessorKey: 'external_location_id' },
    { header: 'State', accessorKey: 'state_region' },
    {
      header: 'Details',
      accessorKey: 'id',
      cell: ({ row }) => (
        <Button variant="ghost" onClick={() => setSelectedFinding(row.original)}>
          View
        </Button>
      ),
    },
  ]

  const handleFindingUpdate = async (patch: { status?: string; disposition?: string }) => {
    if (!selectedFinding) return
    await updateFinding.mutateAsync({ id: selectedFinding.id, ...patch })
    setSelectedFinding({ ...selectedFinding, ...patch })
    findingsQuery.refetch()
  }

  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Referrals & findings</h2>
          <p className="text-sm text-slate-600">Review triggered underwriting rules and manage dispositions.</p>
        </div>
        <div className="grid gap-2 md:grid-cols-4">
          <Select value={selectedExposure?.toString() || ''} onChange={(e) => setSelectedExposure(Number(e.target.value))}>
            <option value="">Exposure version</option>
            {exposures.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name || v.id}
              </option>
            ))}
          </Select>
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Status</option>
            {statusOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </Select>
          <Select value={dispositionFilter} onChange={(e) => setDispositionFilter(e.target.value)}>
            <option value="">Disposition</option>
            {dispositionOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </Select>
          <Select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
            <option value="">Severity</option>
            {severityOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </Select>
          <Select value={targetFilter} onChange={(e) => setTargetFilter(e.target.value)}>
            <option value="">Target</option>
            {targetOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </Select>
          <Input placeholder="Hazard band" value={hazardBandFilter} onChange={(e) => setHazardBandFilter(e.target.value)} />
          <Input placeholder="State/region" value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} />
          <Input placeholder="LOB/Product" value={lobFilter} onChange={(e) => setLobFilter(e.target.value)} />
          <Input placeholder="Search external location ID" value={searchExternal} onChange={(e) => setSearchExternal(e.target.value)} />
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[2fr,1fr]">
        <Card className="space-y-3">
          {filteredFindings.length ? (
            <DataTable data={filteredFindings} columns={columns} />
          ) : (
            <p className="text-sm text-slate-600">No findings found for the selected filters.</p>
          )}
        </Card>

        <Card className="space-y-3">
          <h3 className="text-lg font-semibold">Finding details</h3>
          {selectedFinding ? (
            <>
              <div className="space-y-1 text-sm">
                <div className="flex items-center gap-2">
                  <Badge>{selectedFinding.status}</Badge>
                  <Badge className="bg-slate-100 text-slate-700">{selectedFinding.disposition}</Badge>
                </div>
                <div>Rule: {selectedFinding.rule_name}</div>
                <div>Severity: {selectedFinding.rule_severity}</div>
                <div>Last seen: {formatDate(selectedFinding.last_seen_at)}</div>
              </div>
              <div className="space-y-2">
                <Select
                  value={selectedFinding.disposition}
                  onChange={(e) => handleFindingUpdate({ disposition: e.target.value })}
                >
                  {dispositionOptions.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </Select>
                <div className="flex flex-wrap gap-2">
                  <Button variant="ghost" onClick={() => handleFindingUpdate({ status: 'ACKED' })}>
                    Ack
                  </Button>
                  <Button variant="ghost" onClick={() => handleFindingUpdate({ status: 'RESOLVED' })}>
                    Resolve
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <div className="text-sm font-medium">Why it triggered</div>
                <pre className="rounded-md bg-slate-50 p-2 text-xs">
                  {JSON.stringify(selectedFinding.explanation, null, 2)}
                </pre>
              </div>
              <div className="space-y-2">
                <div className="text-sm font-medium">Notes</div>
                {(notesQuery.data ?? []).map((note) => (
                  <div key={note.id} className="rounded-md border border-slate-200 p-2 text-sm">
                    <div className="text-xs text-slate-500">{formatDate(note.created_at)}</div>
                    <div>{note.note_text}</div>
                  </div>
                ))}
                <Textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder="Add a note" />
                <Button
                  onClick={async () => {
                    if (!noteText.trim() || !selectedFinding) return
                    await createNote.mutateAsync({
                      entity_type: 'FINDING',
                      entity_id: String(selectedFinding.id),
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
            <p className="text-sm text-slate-600">Select a finding to review details.</p>
          )}
        </Card>
      </div>
    </div>
  )
}
