import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { useUnderwritingPacket } from '../api/hooks'
import {
  UnderwritingPacketQueued,
  UnderwritingPacketResponse,
  UnderwritingPacketSuccess,
} from '../api/types'
import { Card } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
import { Badge } from '../components/ui/badge'
import { Skeleton } from '../components/ui/skeleton'
import { Table, TBody, TD, TH, THead, TR } from '../components/ui/table'
import { prettyJson } from '../utils/json'

const DEFAULT_COUNTRY = 'US'
const AUTO_RETRY_LIMIT = 3
const AUTO_RETRY_DELAY_MS = 2000

const decisionTone: Record<string, 'default' | 'success' | 'warn' | 'danger'> = {
  ACCEPT: 'success',
  REFER: 'warn',
  DECLINE: 'danger',
  NEEDS_DATA: 'default',
}

function isQueued(response: UnderwritingPacketResponse | null): response is UnderwritingPacketQueued {
  return Boolean(response && (response as UnderwritingPacketQueued).status === 'ENRICHMENT_QUEUED')
}

function isSuccess(response: UnderwritingPacketResponse | null): response is UnderwritingPacketSuccess {
  return Boolean(response && !isQueued(response))
}

export function UnderwritingWorkbenchPage() {
  const mutation = useUnderwritingPacket()
  const { mutate, isPending } = mutation
  const [response, setResponse] = useState<UnderwritingPacketResponse | null>(null)
  const [requestId, setRequestId] = useState<string | undefined>(undefined)
  const [errorInfo, setErrorInfo] = useState<{ message: string; requestId?: string; code?: string } | null>(null)
  const [autoRetryCount, setAutoRetryCount] = useState(0)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showRawJson, setShowRawJson] = useState(false)
  const [lastPayload, setLastPayload] = useState<Record<string, any> | null>(null)
  const [form, setForm] = useState({
    address_line1: '',
    city: '',
    state_region: '',
    postal_code: '',
    country: DEFAULT_COUNTRY,
    best_effort: true,
    wait_for_enrichment_seconds: 3,
    enrich_mode: 'auto',
    include_decision: true,
  })

  const success = isSuccess(response) ? response : null
  const queued = isQueued(response) ? response : null

  const hazards = (success?.hazards || {}) as Record<string, any>
  const hazardEntries = useMemo(() => {
    return Object.entries(hazards).map(([peril, value]) => ({ peril, ...(value || {}) }))
  }, [hazards])

  const decision = success?.decision as Record<string, any> | undefined
  const explainability = success?.explainability as Record<string, any> | undefined
  const quality = (success?.quality || {}) as Record<string, any>
  const nestedQuality = (quality?.data_quality || {}) as Record<string, any>

  const enrichmentStatus = quality?.enrichment_status || nestedQuality?.enrichment_status
  const enrichmentErrors = quality?.enrichment_errors || nestedQuality?.enrichment_errors
  const completeness = quality?.completeness || nestedQuality?.completeness
  const missingPerils = quality?.peril_missing || nestedQuality?.peril_missing

  const hazardVersions =
    (success?.provenance as Record<string, any> | undefined)?.hazard_versions_used ||
    (success as Record<string, any> | undefined)?.hazard_versions_used ||
    []

  const policyUsed = (success as Record<string, any> | undefined)?.policy_used

  const decisionLabel = decision?.decision || (success?.decision === null ? 'NOT REQUESTED' : 'UNKNOWN')
  const confidencePct = Math.round(Math.max(0, Math.min(1, Number(decision?.confidence ?? 0))) * 100)

  const driverRows = Array.isArray(explainability?.drivers) ? explainability?.drivers : []
  const sortedDrivers = [...driverRows].sort((a: any, b: any) => {
    const diff = Number(b?.contribution_pct ?? 0) - Number(a?.contribution_pct ?? 0)
    if (diff !== 0) return diff
    return String(a?.peril || '').localeCompare(String(b?.peril || ''))
  })

  const structuralImpacts = Array.isArray(explainability?.structural_impacts)
    ? explainability?.structural_impacts
    : []

  const stepStates = [
    { label: 'Resolve address', done: Boolean(response) },
    { label: 'Enrich property', done: Boolean(success?.property?.property_profile_id || quality?.property_enriched || nestedQuality?.property_enriched) },
    { label: 'Join hazards', done: hazardEntries.length > 0 },
    { label: 'Score', done: success?.resilience?.resilience_score !== undefined },
    { label: 'Decide', done: Boolean(decision?.decision) },
  ]

  function handleSubmit(event?: FormEvent) {
    if (event) event.preventDefault()
    if (!form.address_line1 || !form.city || !form.state_region) {
      toast.error('Address line, city, and state are required')
      return
    }
    const payload = {
      address: {
        address_line1: form.address_line1,
        city: form.city,
        state_region: form.state_region,
        postal_code: form.postal_code,
        country: form.country || DEFAULT_COUNTRY,
      },
      best_effort: form.best_effort,
      wait_for_enrichment_seconds: Number(form.wait_for_enrichment_seconds || 0),
      enrich_mode: form.enrich_mode,
      include_decision: form.include_decision,
    }
    setErrorInfo(null)
    mutate(payload, {
      onSuccess: ({ data, requestId: headerRequestId }) => {
        setResponse(data)
        setRequestId(headerRequestId)
        setLastPayload(payload)
        setAutoRetryCount(0)
      },
      onError: (error: any) => {
        const message = error?.message || 'Request failed'
        setErrorInfo({ message, requestId: error?.requestId, code: error?.code })
        toast.error(message)
      },
    })
  }

  function handleRefresh() {
    if (!lastPayload) return
    setErrorInfo(null)
    mutate(lastPayload, {
      onSuccess: ({ data, requestId: headerRequestId }) => {
        setResponse(data)
        setRequestId(headerRequestId)
        setAutoRetryCount(0)
      },
      onError: (error: any) => {
        const message = error?.message || 'Request failed'
        setErrorInfo({ message, requestId: error?.requestId, code: error?.code })
        toast.error(message)
      },
    })
  }

  function handleCopyRequestId() {
    if (!requestId) return
    if (navigator.clipboard) {
      navigator.clipboard.writeText(requestId).then(() => toast.success('Request ID copied'))
      return
    }
    toast.error('Clipboard not available')
  }

  const shouldAutoRetry = Boolean(
    queued && lastPayload && Number(lastPayload.wait_for_enrichment_seconds || 0) > 0
  )

  useEffect(() => {
    if (!queued || isPending || !lastPayload || !shouldAutoRetry) return
    if (autoRetryCount >= AUTO_RETRY_LIMIT) return
    const timer = window.setTimeout(() => {
      setAutoRetryCount((count) => count + 1)
      mutate(lastPayload, {
        onSuccess: ({ data, requestId: headerRequestId }) => {
          setResponse(data)
          setRequestId(headerRequestId)
        },
        onError: (error: any) => {
          const message = error?.message || 'Request failed'
          setErrorInfo({ message, requestId: error?.requestId, code: error?.code })
          toast.error(message)
        },
      })
    }, AUTO_RETRY_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [queued, isPending, lastPayload, autoRetryCount, mutate, shouldAutoRetry])

  const pending = isPending

  return (
    <div className="space-y-4">
      <Card className="flex flex-col gap-3 border-slate-200 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-700 text-white">
        <div className="flex flex-wrap items-center gap-3">
          <Badge className="bg-white/10 text-white">AI Underwriting</Badge>
          <h1 className="text-xl font-semibold">Underwriting Workbench</h1>
          <p className="text-sm text-slate-200">
            Address-only intake with deterministic enrichment, scoring, and decisioning.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {stepStates.map((step) => (
            <span
              key={step.label}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${
                step.done ? 'border-emerald-300/40 bg-emerald-500/20 text-emerald-100' : 'border-white/20 text-slate-200'
              }`}
            >
              <span className={`h-2 w-2 rounded-full ${step.done ? 'bg-emerald-300' : 'bg-slate-400/60'}`} />
              {step.label}
            </span>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <Card className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Address-only underwriting</h2>
            <p className="text-sm text-slate-600">Enter an address and generate an underwriting packet.</p>
          </div>
          <form className="space-y-3" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase text-slate-500">Address line</label>
              <Input
                placeholder="123 Market St"
                value={form.address_line1}
                onChange={(e) => setForm((prev) => ({ ...prev, address_line1: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase text-slate-500">City</label>
                <Input
                  placeholder="San Francisco"
                  value={form.city}
                  onChange={(e) => setForm((prev) => ({ ...prev, city: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase text-slate-500">State</label>
                <Input
                  placeholder="CA"
                  value={form.state_region}
                  onChange={(e) => setForm((prev) => ({ ...prev, state_region: e.target.value }))}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase text-slate-500">Postal code</label>
                <Input
                  placeholder="94105"
                  value={form.postal_code}
                  onChange={(e) => setForm((prev) => ({ ...prev, postal_code: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase text-slate-500">Country</label>
                <Input
                  placeholder="US"
                  value={form.country}
                  onChange={(e) => setForm((prev) => ({ ...prev, country: e.target.value }))}
                />
              </div>
            </div>

            <button
              type="button"
              className="text-left text-sm font-medium text-blue-600 hover:text-blue-700"
              onClick={() => setShowAdvanced((value) => !value)}
            >
              {showAdvanced ? 'Hide advanced options' : 'Show advanced options'}
            </button>

            {showAdvanced ? (
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-600">Best effort</span>
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={form.best_effort}
                    onChange={(e) => setForm((prev) => ({ ...prev, best_effort: e.target.checked }))}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase text-slate-500">Wait for enrichment (seconds)</label>
                  <Input
                    type="number"
                    min={0}
                    value={form.wait_for_enrichment_seconds}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        wait_for_enrichment_seconds: Number(e.target.value),
                      }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase text-slate-500">Enrichment mode</label>
                  <Select
                    value={form.enrich_mode}
                    onChange={(e) => setForm((prev) => ({ ...prev, enrich_mode: e.target.value }))}
                  >
                    <option value="auto">Auto</option>
                    <option value="sync">Sync</option>
                    <option value="async">Async</option>
                  </Select>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-600">Include decision</span>
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={form.include_decision}
                    onChange={(e) => setForm((prev) => ({ ...prev, include_decision: e.target.checked }))}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-600">Show raw JSON</span>
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={showRawJson}
                    onChange={(e) => setShowRawJson(e.target.checked)}
                  />
                </div>
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={pending}>
                {pending ? 'Generating...' : 'Generate Underwriting Packet'}
              </Button>
              <Button type="button" variant="secondary" onClick={handleRefresh} disabled={!lastPayload || pending}>
                Refresh
              </Button>
            </div>
          </form>

          <div className="space-y-2 rounded-lg border border-dashed border-slate-200 p-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Request ID</span>
              {requestId ? (
                <Button variant="secondary" className="px-2 py-1 text-xs" onClick={handleCopyRequestId}>
                  Copy
                </Button>
              ) : null}
            </div>
            <p className="font-mono text-xs text-slate-700">{requestId || 'No request yet'}</p>
          </div>
        </Card>

        <div className="space-y-4">
          {pending ? (
            <Card className="space-y-3">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-24 w-full" />
            </Card>
          ) : null}

          {errorInfo ? (
            <Card className="border border-red-200 bg-red-50 text-sm text-red-700">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">Request failed</span>
                {errorInfo.code ? <Badge tone="danger">{errorInfo.code}</Badge> : null}
              </div>
              <p>{errorInfo.message}</p>
              {errorInfo.requestId ? <p className="text-xs text-red-600">Request ID: {errorInfo.requestId}</p> : null}
            </Card>
          ) : null}

          {queued ? (
            <Card className="space-y-3 border border-amber-200 bg-amber-50">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-amber-900">Enrichment queued</h3>
                  <p className="text-sm text-amber-700">We are enriching the property. You can retry now.</p>
                </div>
                <Badge tone="warn">QUEUED</Badge>
              </div>
              <div className="text-sm text-amber-700">
                <p>Run ID: {queued.run_id}</p>
                {queued.message ? <p>{queued.message}</p> : null}
                {autoRetryCount > 0 ? <p>Auto-retries: {autoRetryCount}/{AUTO_RETRY_LIMIT}</p> : null}
                {shouldAutoRetry ? <p className="animate-pulse text-xs text-amber-600">Waiting for enrichment...</p> : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={handleRefresh} disabled={pending || !lastPayload}>
                  Retry now
                </Button>
                <Button variant="secondary" onClick={() => setResponse(null)}>
                  Dismiss
                </Button>
              </div>
            </Card>
          ) : null}

          {success ? (
            <>
              <Card className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-lg font-semibold">Decision</h3>
                    <p className="text-sm text-slate-600">Resilience score: {success?.resilience?.resilience_score ?? 'N/A'}</p>
                  </div>
                  <Badge tone={decisionTone[String(decisionLabel)] || 'default'}>{decisionLabel}</Badge>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>Confidence</span>
                    <span>{confidencePct}%</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-200">
                    <div
                      className="h-2 rounded-full bg-blue-600"
                      style={{ width: `${confidencePct}%` }}
                    />
                  </div>
                </div>
                <div className="grid gap-3 lg:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold uppercase text-slate-500">Reason codes</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {(decision?.reason_codes || []).length ? (
                        decision?.reason_codes?.map((code: string) => <Badge key={code}>{code}</Badge>)
                      ) : (
                        <span className="text-sm text-slate-500">None</span>
                      )}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase text-slate-500">Reasons</p>
                    <ul className="mt-2 space-y-1 text-sm text-slate-600">
                      {(decision?.reasons || []).length ? (
                        decision?.reasons?.map((reason: string) => <li key={reason}>{reason}</li>)
                      ) : (
                        <li>No reasons provided.</li>
                      )}
                    </ul>
                  </div>
                </div>
                {Array.isArray(decision?.mitigation_recommendations) && decision?.mitigation_recommendations.length ? (
                  <div>
                    <p className="text-xs font-semibold uppercase text-slate-500">Mitigation recommendations</p>
                    <div className="mt-2 grid gap-2 lg:grid-cols-2">
                      {decision?.mitigation_recommendations?.map((rec: any, idx: number) => (
                        <div key={`${rec?.code || 'rec'}-${idx}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                          <p className="text-sm font-semibold text-slate-700">{rec?.title || rec?.code}</p>
                          <p className="text-sm text-slate-600">{rec?.detail}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </Card>

              <Card className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">AI Summary</h3>
                  <Badge className="bg-blue-100 text-blue-700">Explainability</Badge>
                </div>
                <p className="text-base font-medium text-slate-800">{explainability?.narrative || 'No narrative available.'}</p>
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">Top drivers</p>
                  <div className="mt-2 grid gap-2 lg:grid-cols-2">
                    {sortedDrivers.length ? (
                      sortedDrivers.slice(0, 4).map((driver: any, idx: number) => (
                        <div key={`${driver?.peril || 'driver'}-${idx}`} className="rounded-lg border border-slate-200 bg-white p-3">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold text-slate-700">{driver?.peril || 'Unknown'}</span>
                            <Badge>{Math.round(Number(driver?.contribution_pct || 0) * 100)}%</Badge>
                          </div>
                          <p className="text-xs text-slate-500">Contribution: {(driver?.contribution || 0).toFixed?.(3) ?? driver?.contribution}</p>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">No driver data available.</p>
                    )}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">Structural impacts</p>
                  <div className="mt-2 space-y-2 text-sm text-slate-600">
                    {structuralImpacts.length ? (
                      structuralImpacts.map((impact: any, idx: number) => (
                        <div key={`impact-${idx}`} className="flex items-start justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 p-2">
                          <span>{impact?.label || impact?.type || 'Impact'}</span>
                          <Badge>{impact?.delta ?? impact?.value ?? 'n/a'}</Badge>
                        </div>
                      ))
                    ) : (
                      <p>No structural adjustments detected.</p>
                    )}
                  </div>
                </div>
              </Card>

              <Card className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">Data quality</h3>
                  {enrichmentStatus ? <Badge>{enrichmentStatus}</Badge> : null}
                </div>
                <div className="grid gap-3 lg:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold uppercase text-slate-500">Completeness</p>
                    <div className="mt-2 space-y-1 text-sm text-slate-600">
                      {completeness ? (
                        Object.entries(completeness).map(([key, value]) => (
                          <div key={key} className="flex items-center justify-between">
                            <span>{key}</span>
                            <Badge tone={value ? 'success' : 'warn'}>{value ? 'Yes' : 'No'}</Badge>
                          </div>
                        ))
                      ) : (
                        <p>No completeness data.</p>
                      )}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase text-slate-500">Enrichment status</p>
                    <div className="mt-2 space-y-1 text-sm text-slate-600">
                      <p>Status: {enrichmentStatus || 'Unknown'}</p>
                      {Array.isArray(enrichmentErrors) && enrichmentErrors.length ? (
                        <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-700">
                          {enrichmentErrors.map((err: any, idx: number) => (
                            <p key={`err-${idx}`}>{err?.message || err?.code || 'Unknown enrichment error'}</p>
                          ))}
                        </div>
                      ) : null}
                      {Array.isArray(missingPerils) && missingPerils.length ? (
                        <p className="text-xs text-amber-700">Missing perils: {missingPerils.join(', ')}</p>
                      ) : null}
                    </div>
                  </div>
                </div>
              </Card>

              <Card className="space-y-3">
                <h3 className="text-lg font-semibold">Hazards</h3>
                {hazardEntries.length ? (
                  <Table>
                    <THead>
                      <TR>
                        <TH>Peril</TH>
                        <TH>Score</TH>
                        <TH>Band</TH>
                        <TH>Source</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {hazardEntries.map((hazard) => (
                        <TR key={hazard.peril}>
                          <TD>{hazard.peril}</TD>
                          <TD>{hazard.score ?? 'n/a'}</TD>
                          <TD>{hazard.band ?? 'n/a'}</TD>
                          <TD className="max-w-[240px] truncate" title={hazard.source || ''}>
                            {hazard.source || 'n/a'}
                          </TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                ) : (
                  <p className="text-sm text-slate-500">No hazard data.</p>
                )}
                {Array.isArray(hazardVersions) && hazardVersions.length ? (
                  <div>
                    <p className="text-xs font-semibold uppercase text-slate-500">Hazard versions used</p>
                    <div className="mt-2 grid gap-2 lg:grid-cols-2">
                      {hazardVersions.map((version: any) => (
                        <div
                          key={`${version?.hazard_dataset_id || 'dataset'}-${version?.hazard_dataset_version_id || 'version'}`}
                          className="rounded-md border border-slate-200 bg-slate-50 p-2 text-xs text-slate-600"
                        >
                          <p className="font-semibold text-slate-700">{version?.hazard_dataset_name || version?.peril}</p>
                          <p>Version: {version?.version_label || version?.hazard_dataset_version_id}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </Card>

              <Card className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">Provenance</h3>
                  <Badge className="bg-slate-100 text-slate-700">Audit</Badge>
                </div>
                <div className="grid gap-2 text-sm text-slate-600 lg:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold uppercase text-slate-500">Scoring version</p>
                    <p>{success?.provenance?.scoring_version || 'n/a'}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase text-slate-500">Code version</p>
                    <p>{success?.provenance?.code_version || 'n/a'}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase text-slate-500">Policy</p>
                    <p>{policyUsed?.version_label || policyUsed?.policy_pack_version_id || 'default'}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase text-slate-500">Property profile</p>
                    <p>{success?.property?.property_profile_id || 'n/a'}</p>
                  </div>
                </div>
              </Card>
            </>
          ) : null}

          {showRawJson && response ? (
            <Card>
              <pre className="max-h-[520px] overflow-auto rounded bg-slate-900 p-4 text-xs text-slate-100">
                {prettyJson(response)}
              </pre>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  )
}
