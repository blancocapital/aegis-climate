import { useEffect, useMemo, useState } from 'react'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { v4 as uuidv4 } from 'uuid'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Card } from '../components/ui/card'
import { Textarea } from '../components/ui/textarea'
import { useCommitUpload, useCreateMapping, useRun, useUploadFile, useValidateUpload } from '../api/hooks'
import { Badge } from '../components/ui/badge'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'
import { toast } from 'sonner'
import { useNavigate } from 'react-router-dom'
import { prettyJson, safeJsonParse } from '../utils/json'

const mappingSchema = z.object({
  name: z.string().min(1),
  mapping_json: z.string().min(2),
})

type MappingForm = z.infer<typeof mappingSchema>

type Issue = { id: number; message: string; severity: string }

export function IngestionWizardPage() {
  const [uploadId, setUploadId] = useState<string | null>(null)
  const [runId, setRunId] = useState<number | null>(null)
  const [commitRunId, setCommitRunId] = useState<number | null>(null)
  const [issues, setIssues] = useState<Issue[]>([])
  const [stats, setStats] = useState<Record<string, number>>({})
  const uploadMutation = useUploadFile()
  const mappingMutation = useCreateMapping(uploadId || undefined)
  const validateMutation = useValidateUpload(uploadId || undefined)
  const commitMutation = useCommitUpload(uploadId || undefined)
  const runQuery = useRun(runId || undefined, Boolean(runId))
  const commitRunQuery = useRun(commitRunId || undefined, Boolean(commitRunId))
  const navigate = useNavigate()

  const mappingForm = useForm<MappingForm>({ resolver: zodResolver(mappingSchema), defaultValues: { name: 'Auto mapping', mapping_json: '' } })

  const handleFileChange = async (file?: File) => {
    if (!file) return
    const idempotencyKey = uuidv4()
    const res = await uploadMutation.mutateAsync({ file, idempotencyKey })
    toast.success(`Uploaded ${file.name}`)
    setUploadId(res.upload_id)
  }

  const generateIdentityMapping = () => {
    const sample = {
      external_location_id: 'external_location_id',
      address: 'address',
      city: 'city',
      state: 'state',
      country: 'country',
      latitude: 'latitude',
      longitude: 'longitude',
      tiv: 'tiv',
    }
    mappingForm.setValue('mapping_json', prettyJson(sample))
  }

  const submitMapping = async (values: MappingForm) => {
    const parsed = safeJsonParse(values.mapping_json)
    if (!parsed) {
      toast.error('Invalid JSON')
      return
    }
    await mappingMutation.mutateAsync({ name: values.name, mapping_json: parsed })
    toast.success('Mapping saved')
  }

  const startValidation = async () => {
    const res = await validateMutation.mutateAsync()
    setRunId(res.run_id)
  }

  const startCommit = async () => {
    const res = await commitMutation.mutateAsync({})
    setCommitRunId(res.run_id)
  }

  useEffect(() => {
    if (runQuery.data?.output_refs_json) {
      const counts = runQuery.data.output_refs_json.validation_summary || {}
      setStats(counts)
      const runIssues: Issue[] = (runQuery.data.output_refs_json.issues || []).map((issue: any, idx: number) => ({
        id: idx,
        message: issue.message || 'Issue',
        severity: issue.severity || 'WARN',
      }))
      setIssues(runIssues)
    }
  }, [runQuery.data])

  useEffect(() => {
    const id = commitRunQuery.data?.output_refs_json?.exposure_version_id
    if (commitRunQuery.data?.status === 'SUCCEEDED' && id) {
      toast.success('Exposure committed')
      navigate(`/exposure-versions/${id}`)
    }
  }, [commitRunQuery.data])

  const issueColumns: ColumnDef<Issue>[] = [
    { header: 'Severity', accessorKey: 'severity' },
    { header: 'Message', accessorKey: 'message' },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Upload wizard</h2>
        {uploadId && <Badge tone="success">Upload ID {uploadId}</Badge>}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Step 1 · Upload CSV</p>
              <p className="text-xs text-slate-500">Send to /uploads with Idempotency-Key</p>
            </div>
            <input type="file" accept=".csv" onChange={(e) => handleFileChange(e.target.files?.[0])} />
          </div>
          {uploadMutation.isLoading && <p className="text-sm">Uploading...</p>}
        </Card>

        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Step 2 · Mapping</p>
              <p className="text-xs text-slate-500">Define mapping JSON</p>
            </div>
            <Button variant="ghost" onClick={generateIdentityMapping}>
              Auto mapping
            </Button>
          </div>
          <form className="space-y-2" onSubmit={mappingForm.handleSubmit(submitMapping)}>
            <Input placeholder="Name" {...mappingForm.register('name')} />
            <Textarea rows={6} {...mappingForm.register('mapping_json')} placeholder='{"external_location_id": "external_location_id"}' />
            <Button type="submit" disabled={!uploadId || mappingMutation.isLoading}>
              {mappingMutation.isLoading ? 'Saving...' : 'Save mapping'}
            </Button>
          </form>
        </Card>

        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Step 3 · Validate</p>
              <p className="text-xs text-slate-500">/uploads/{'{upload_id}'}/validate</p>
            </div>
            <Button onClick={startValidation} disabled={!uploadId || validateMutation.isLoading}>
              {validateMutation.isLoading ? 'Starting...' : 'Validate'}
            </Button>
          </div>
          {runId && (
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Badge tone={runQuery.data?.status === 'SUCCEEDED' ? 'success' : runQuery.data?.status === 'FAILED' ? 'danger' : 'warn'}>
                  {runQuery.data?.status || 'PENDING'}
                </Badge>
                <span>Run ID {runId}</span>
              </div>
              {stats && (
                <div className="flex gap-3 text-xs text-slate-700">
                  <span>Errors: {stats.ERROR || 0}</span>
                  <span>Warn: {stats.WARN || 0}</span>
                  <span>Info: {stats.INFO || 0}</span>
                  <span>Total rows: {stats.total_rows || '-'}</span>
                </div>
              )}
              {issues.length > 0 ? <DataTable data={issues} columns={issueColumns} /> : <p>No issues yet.</p>}
            </div>
          )}
        </Card>

        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Step 4 · Commit</p>
              <p className="text-xs text-slate-500">Commit when errors are 0</p>
            </div>
            <Button
              variant="primary"
              onClick={startCommit}
              disabled={!uploadId || (stats.ERROR ?? 1) > 0 || commitMutation.isLoading}
            >
              {commitMutation.isLoading ? 'Starting...' : 'Commit'}
            </Button>
          </div>
          {commitRunId && (
            <div className="space-y-1 text-sm">
              <p>
                Status: <Badge>{commitRunQuery.data?.status || 'PENDING'}</Badge>
              </p>
              <p>Run ID {commitRunId}</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
