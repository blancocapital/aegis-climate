import { useMemo, useState } from 'react'
import { Card } from '../components/ui/card'
import { Select } from '../components/ui/select'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Input } from '../components/ui/input'
import { Textarea } from '../components/ui/textarea'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'
import { apiRequest } from '../api/client'
import {
  useBreaches,
  useCreateRollup,
  useCreateUWDecision,
  useCreateUWNote,
  useExposureVersions,
  useRun,
  useRunUWEval,
  useRollupConfigs,
  useUWFindingList,
  useUWSummary,
  useUWDecisions,
} from '../api/hooks'
import { UWFinding } from '../api/types'
import { formatDate } from '../utils/date'
import { formatNumber } from '../utils/format'

const readinessStyles: Record<string, string> = {
  READY: 'bg-emerald-100 text-emerald-700',
  'NEEDS REVIEW': 'bg-amber-100 text-amber-700',
  'NOT READY': 'bg-rose-100 text-rose-700',
}

const decisionOptions = ['PROCEED', 'REFER', 'PROCEED_WITH_CONDITIONS', 'DECLINE']

export function SubmissionWorkbenchPage() {
  const { data: exposures = [] } = useExposureVersions()
  const [selectedExposure, setSelectedExposure] = useState<number | null>(null)
  const summary = useUWSummary(selectedExposure ?? undefined)
  const findingsQuery = useUWFindingList({ exposure_version_id: selectedExposure ?? undefined })
  const findings = findingsQuery.data ?? []
  const breachesQuery = useBreaches({ exposure_version_id: selectedExposure ?? undefined, status_filter: 'OPEN' })
  const breaches = breachesQuery.data ?? []
  const decisionsQuery = useUWDecisions({ exposure_version_id: selectedExposure ?? undefined })
  const createDecision = useCreateUWDecision()
  const runUWEval = useRunUWEval()
  const createRollup = useCreateRollup()
  const { data: rollupConfigs = [] } = useRollupConfigs()

  const [geocodeRunId, setGeocodeRunId] = useState<number | null>(null)
  const [rollupRunId, setRollupRunId] = useState<number | null>(null)
  const [uwRunId, setUwRunId] = useState<number | null>(null)

  const geocodeRun = useRun(geocodeRunId ?? undefined, Boolean(geocodeRunId))
  const rollupRun = useRun(rollupRunId ?? undefined, Boolean(rollupRunId))
  const uwRun = useRun(uwRunId ?? undefined, Boolean(uwRunId))

  const [rollupConfigId, setRollupConfigId] = useState<number | null>(null)
  const [rollupOverlayIds, setRollupOverlayIds] = useState<string>('')
  const [uwRollupResultId, setUwRollupResultId] = useState<string>('')

  const [decisionValue, setDecisionValue] = useState<string>('PROCEED')
  const [decisionConditions, setDecisionConditions] = useState<string>('')
  const [decisionRationale, setDecisionRationale] = useState<string>('')
  const [noteText, setNoteText] = useState<string>('')
  const createNote = useCreateUWNote()

  const readiness = useMemo(() => {
    const summaryData = summary.data
    const validation = summaryData?.data_quality?.validation_warn_error_counts || {}
    const tierCounts = summaryData?.data_quality?.tier_counts || {}
    const total = Object.values(tierCounts).reduce((acc: number, val: any) => acc + Number(val || 0), 0)
    const tierC = Number((tierCounts as Record<string, number>)['C'] || 0)
    const lowConfidence = Number(summaryData?.data_quality?.low_confidence_count || 0)
    if (validation.ERROR && validation.ERROR > 0) return 'NOT READY'
    if (total > 0 && tierC / total > 0.1) return 'NEEDS REVIEW'
    if (lowConfidence > 0) return 'NEEDS REVIEW'
    return 'READY'
  }, [summary.data])

  const hazardMix = summary.data?.hazard_mix?.by_band || []
  const highHazardCount = hazardMix
    .filter((b: any) => ['HIGH', 'EXTREME'].includes(String(b.band || '').toUpperCase()))
    .reduce((acc: number, b: any) => acc + Number(b.count || 0), 0)

  const findingsColumns: ColumnDef<UWFinding>[] = [
    { header: 'Status', accessorKey: 'status' },
    { header: 'Disposition', accessorKey: 'disposition' },
    { header: 'Rule', accessorKey: 'rule_name' },
    { header: 'Severity', accessorKey: 'rule_severity' },
    { header: 'Target', accessorKey: 'rule_target' },
    { header: 'Location', accessorKey: 'external_location_id' },
    { header: 'Rollup', accessorKey: 'rollup_key_hash' },
  ]

  const triggerGeocode = async () => {
    if (!selectedExposure) return
    const res = await apiRequest<{ run_id: number }>({
      method: 'POST',
      path: `/exposure-versions/${selectedExposure}/geocode`,
    })
    setGeocodeRunId(res.run_id)
  }

  const triggerRollup = async () => {
    if (!selectedExposure || !rollupConfigId) return
    const overlayIds = rollupOverlayIds
      .split(',')
      .map((id) => Number(id.trim()))
      .filter((id) => !Number.isNaN(id))
    const res = await createRollup.mutateAsync({
      exposure_version_id: selectedExposure,
      rollup_config_id: rollupConfigId,
      hazard_overlay_result_ids: overlayIds,
    })
    setRollupRunId(res.run_id)
  }

  const triggerUwEval = async () => {
    if (!selectedExposure) return
    const rollupResultId = uwRollupResultId ? Number(uwRollupResultId) : undefined
    const res = await runUWEval.mutateAsync({
      exposure_version_id: selectedExposure,
      rollup_result_id: rollupResultId,
    })
    setUwRunId(res.run_id)
    if (selectedExposure) {
      findingsQuery.refetch()
    }
  }

  const submitDecision = async () => {
    if (!selectedExposure) return
    const conditions = decisionConditions
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
    await createDecision.mutateAsync({
      exposure_version_id: selectedExposure,
      decision: decisionValue,
      conditions_json: conditions,
      rationale_text: decisionRationale,
    })
    decisionsQuery.refetch()
  }

  const currentDecision = decisionsQuery.data?.[0]

  return (
    <div className="space-y-4">
      <Card className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-semibold">Submission workbench</h2>
          <p className="text-sm text-slate-600">
            Intake → data quality → hazards → concentrations → referrals → decision.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Select value={selectedExposure?.toString() || ''} onChange={(e) => setSelectedExposure(Number(e.target.value))}>
            <option value="">Select exposure version</option>
            {exposures.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name || v.id}
              </option>
            ))}
          </Select>
          <Badge className={readinessStyles[readiness]}>{readiness}</Badge>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="space-y-2">
          <h3 className="text-lg font-semibold">Readiness & data quality</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>Tier counts: {JSON.stringify(summary.data?.data_quality?.tier_counts || {})}</div>
            <div>Low geo confidence: {summary.data?.data_quality?.low_confidence_count ?? 0}</div>
            <div>Validation: {JSON.stringify(summary.data?.data_quality?.validation_warn_error_counts || {})}</div>
            <div>High hazard count: {highHazardCount}</div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-slate-600">
            <span>Open breaches: {summary.data?.controls?.open_breaches ?? 0}</span>
            <span>Open findings: {summary.data?.controls?.open_uw_findings ?? 0}</span>
          </div>
        </Card>

        <Card className="space-y-2">
          <h3 className="text-lg font-semibold">Next actions</h3>
          <div className="flex flex-wrap gap-2">
            <Button onClick={triggerGeocode} disabled={!selectedExposure}>
              Run geocode
            </Button>
            {geocodeRunId && <Badge>{geocodeRun.data?.status || 'PENDING'}</Badge>}
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium">Rollup</div>
            <Select value={rollupConfigId?.toString() || ''} onChange={(e) => setRollupConfigId(Number(e.target.value))}>
              <option value="">Select rollup config</option>
              {rollupConfigs.map((cfg) => (
                <option key={cfg.id} value={cfg.id}>
                  {cfg.name} v{cfg.version}
                </option>
              ))}
            </Select>
            <Input
              placeholder="Overlay result IDs (comma separated)"
              value={rollupOverlayIds}
              onChange={(e) => setRollupOverlayIds(e.target.value)}
            />
            <div className="flex items-center gap-2">
              <Button onClick={triggerRollup} disabled={!selectedExposure || !rollupConfigId || createRollup.isPending}>
                {createRollup.isPending ? 'Starting...' : 'Run rollup'}
              </Button>
              {rollupRunId && <Badge>{rollupRun.data?.status || 'PENDING'}</Badge>}
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium">Underwriting evaluation</div>
            <Input
              placeholder="Rollup result ID (optional)"
              value={uwRollupResultId}
              onChange={(e) => setUwRollupResultId(e.target.value)}
            />
            <div className="flex items-center gap-2">
              <Button onClick={triggerUwEval} disabled={!selectedExposure || runUWEval.isPending}>
                {runUWEval.isPending ? 'Starting...' : 'Run UW eval'}
              </Button>
              {uwRunId && <Badge>{uwRun.data?.status || 'PENDING'}</Badge>}
            </div>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-2">
          <h3 className="text-lg font-semibold">Risk highlights</h3>
          {summary.data?.hazard_mix?.needs_overlay ? (
            <p className="text-sm text-slate-600">No overlay found. Run hazard overlay to populate hazard mix.</p>
          ) : (
            <div className="space-y-2 text-sm">
              <div>By band:</div>
              <div className="flex flex-wrap gap-2">
                {(summary.data?.hazard_mix?.by_band || []).map((item: any) => (
                  <Badge key={`${item.band}-${item.count}`} className="bg-slate-100 text-slate-700">
                    {item.band}: {item.count}
                  </Badge>
                ))}
              </div>
              <div>By category:</div>
              <div className="flex flex-wrap gap-2">
                {(summary.data?.hazard_mix?.by_category || []).map((item: any) => (
                  <Badge key={`${item.category}-${item.count}`} className="bg-slate-100 text-slate-700">
                    {item.category}: {item.count}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card className="space-y-2">
          <h3 className="text-lg font-semibold">Concentrations</h3>
          {summary.data?.concentration?.needs_rollup ? (
            <p className="text-sm text-slate-600">No rollup found. Run rollup to view top concentrations.</p>
          ) : (
            <div className="space-y-2 text-sm">
              {(summary.data?.concentration?.top_keys || []).map((item: any) => (
                <div key={item.rollup_key_hash} className="flex items-center justify-between rounded-md border border-slate-200 px-2 py-1">
                  <div className="truncate text-slate-700">{JSON.stringify(item.rollup_key)}</div>
                  <div className="text-right text-slate-600">
                    <div>TIV {formatNumber(item.tiv_sum)}</div>
                    <div>Count {item.count ?? '-'}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Referrals & conditions</h3>
            <p className="text-sm text-slate-600">
              Open findings and triggered rules for this submission.
            </p>
          </div>
          <div className="text-sm text-slate-600">
            Updated {formatDate(findings[0]?.last_seen_at)}
          </div>
        </div>
        {findings.length ? (
          <DataTable data={findings} columns={findingsColumns} />
        ) : (
          <p className="text-sm text-slate-600">No findings yet. Run UW eval to populate.</p>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3">
          <h3 className="text-lg font-semibold">Decision</h3>
          <div className="text-sm text-slate-600">
            {currentDecision
              ? `Last decision ${currentDecision.decision} · ${formatDate(currentDecision.created_at)}`
              : 'No decision recorded yet.'}
          </div>
          <Select value={decisionValue} onChange={(e) => setDecisionValue(e.target.value)}>
            {decisionOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </Select>
          <Textarea
            placeholder="Conditions (one per line)"
            value={decisionConditions}
            onChange={(e) => setDecisionConditions(e.target.value)}
          />
          <Textarea
            placeholder="Decision rationale"
            value={decisionRationale}
            onChange={(e) => setDecisionRationale(e.target.value)}
          />
          <Button onClick={submitDecision} disabled={!selectedExposure || !decisionRationale}>
            Record decision
          </Button>
        </Card>

        <Card className="space-y-3">
          <h3 className="text-lg font-semibold">Notes</h3>
          <p className="text-sm text-slate-600">
            Capture submission-level notes for audit trail.
          </p>
          <Textarea
            placeholder="Add a note tied to this exposure version"
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
          />
          <Button
            onClick={async () => {
              if (!selectedExposure || !noteText.trim()) return
              await createNote.mutateAsync({
                entity_type: 'EXPOSURE_VERSION',
                entity_id: String(selectedExposure),
                note_text: noteText.trim(),
              })
              setNoteText('')
            }}
            disabled={!selectedExposure || !noteText.trim()}
          >
            Add note
          </Button>
        </Card>
      </div>

      <Card className="space-y-2">
        <h3 className="text-lg font-semibold">Portfolio controls</h3>
        {breaches.length ? (
          <div className="text-sm text-slate-600">
            {breaches.length} open breaches in this exposure version.
          </div>
        ) : (
          <div className="text-sm text-slate-600">No open breaches detected.</div>
        )}
      </Card>
    </div>
  )
}
