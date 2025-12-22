import { useParams } from 'react-router-dom'
import { ColumnDef } from '@tanstack/react-table'
import { useState } from 'react'
import { useExposureLocations, useExposureVersion } from '../api/hooks'
import { ExposureLocation } from '../api/types'
import { Card } from '../components/ui/card'
import { DataTable } from '../components/DataTable'
import { formatDate } from '../utils/date'
import { formatNumber } from '../utils/format'
import { Button } from '../components/ui/button'
import { apiRequest } from '../api/client'
import { useRun } from '../api/hooks'
import { Badge } from '../components/ui/badge'

export function ExposureVersionDetailPage() {
  const { id } = useParams()
  const { data } = useExposureVersion(id)
  const { data: locations = [] } = useExposureLocations(id, { limit: 100 })
  const [geocodeRunId, setGeocodeRunId] = useState<number | null>(null)
  const runQuery = useRun(geocodeRunId || undefined, Boolean(geocodeRunId))

  const triggerGeocode = async () => {
    const res = await apiRequest<{ run_id: number }>({ method: 'POST', path: `/exposure-versions/${id}/geocode` })
    setGeocodeRunId(res.run_id)
  }

  const columns: ColumnDef<ExposureLocation>[] = [
    { header: 'External ID', accessorKey: 'external_location_id' },
    { header: 'Address', accessorKey: 'address_line1' },
    { header: 'City', accessorKey: 'city' },
    { header: 'State', accessorKey: 'state_region' },
    { header: 'Country', accessorKey: 'country' },
    { header: 'Lat', accessorKey: 'latitude' },
    { header: 'Lon', accessorKey: 'longitude' },
    { header: 'TIV', accessorKey: 'tiv' },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Exposure version {id}</h2>
          <p className="text-sm text-slate-600">Created {formatDate(data?.created_at)}</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={triggerGeocode}>Run geocode + quality</Button>
          {geocodeRunId && <Badge>{runQuery.data?.status || 'PENDING'}</Badge>}
        </div>
      </div>
      <Card className="grid grid-cols-2 gap-2 text-sm">
        <div>Locations: {data?.location_count ?? '-'}</div>
        <div>TIV sum: {formatNumber(data?.tiv_sum)}</div>
        <div>Upload: {data?.upload_id}</div>
      </Card>
      <Card className="space-y-2">
        <h3 className="text-lg font-semibold">Locations</h3>
        <DataTable data={locations} columns={columns} />
      </Card>
    </div>
  )
}
