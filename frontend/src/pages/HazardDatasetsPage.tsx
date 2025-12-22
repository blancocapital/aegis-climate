import { useForm } from 'react-hook-form'
import { ColumnDef } from '@tanstack/react-table'
import { useCreateHazardDataset, useHazardDatasetVersions, useHazardDatasets, useUploadHazardVersion } from '../api/hooks'
import { HazardDataset, HazardDatasetVersion } from '../api/types'
import { Card } from '../components/ui/card'
import { DataTable } from '../components/DataTable'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { useState } from 'react'
import { Select } from '../components/ui/select'
import { formatDate } from '../utils/date'
import { toast } from 'sonner'

export function HazardDatasetsPage() {
  const { data: datasets = [], refetch } = useHazardDatasets()
  const [selected, setSelected] = useState<number | null>(null)
  const versions = useHazardDatasetVersions(selected || undefined)
  const createDataset = useCreateHazardDataset()
  const uploadVersion = useUploadHazardVersion(selected || undefined)
  const { register, handleSubmit, reset } = useForm<{ name: string; description?: string }>()

  const datasetColumns: ColumnDef<HazardDataset>[] = [
    { header: 'ID', accessorKey: 'id' },
    { header: 'Name', accessorKey: 'name' },
    { header: 'Created', accessorKey: 'created_at', cell: ({ getValue }) => formatDate(getValue() as string) },
  ]

  const versionColumns: ColumnDef<HazardDatasetVersion>[] = [
    { header: 'ID', accessorKey: 'id' },
    { header: 'Checksum', accessorKey: 'checksum' },
    { header: 'Created', accessorKey: 'created_at', cell: ({ getValue }) => formatDate(getValue() as string) },
  ]

  const onCreate = async (values: { name: string; description?: string }) => {
    await createDataset.mutateAsync(values)
    reset()
    refetch()
  }

  const onUpload = async (file?: File) => {
    if (!file || !selected) return
    await uploadVersion.mutateAsync({ file })
    versions.refetch()
    toast.success('Version uploaded')
  }

  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <h2 className="text-lg font-semibold">Hazard datasets</h2>
        <form className="flex flex-wrap items-end gap-2" onSubmit={handleSubmit(onCreate)}>
          <Input placeholder="Name" {...register('name')} />
          <Input placeholder="Description" {...register('description')} />
          <Button type="submit">Create</Button>
        </form>
        <DataTable data={datasets} columns={datasetColumns} />
      </Card>
      <Card className="space-y-3">
        <div className="flex items-center gap-3">
          <div>
            <h3 className="text-lg font-semibold">Dataset versions</h3>
            <p className="text-sm text-slate-600">Upload GeoJSON to create a new version.</p>
          </div>
          <Select value={selected?.toString() || ''} onChange={(e) => setSelected(Number(e.target.value))}>
            <option value="">Select dataset</option>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
          <input type="file" accept=".json,.geojson" onChange={(e) => onUpload(e.target.files?.[0])} />
        </div>
        {selected ? <DataTable data={versions.data || []} columns={versionColumns} /> : <p>Select a dataset to view versions.</p>}
      </Card>
    </div>
  )
}
