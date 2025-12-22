import { Link } from 'react-router-dom'
import { useExposureVersions } from '../api/hooks'
import { Card } from '../components/ui/card'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'
import { ExposureVersion } from '../api/types'
import { formatDate } from '../utils/date'
import { formatNumber } from '../utils/format'

export function ExposureVersionsPage() {
  const { data = [], isLoading } = useExposureVersions()

  const columns: ColumnDef<ExposureVersion>[] = [
    {
      header: 'Name',
      accessorKey: 'name',
      cell: ({ row }) => <Link className="text-blue-600 hover:underline" to={`/exposure-versions/${row.original.id}`}>{row.original.name || 'Exposure'}</Link>,
    },
    { header: 'ID', accessorKey: 'id' },
    { header: 'Locations', accessorKey: 'location_count' },
    { header: 'TIV', accessorKey: 'tiv_sum', cell: ({ getValue }) => formatNumber(getValue() as number) },
    { header: 'Created', accessorKey: 'created_at', cell: ({ getValue }) => formatDate(getValue() as string) },
  ]

  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Exposure versions</h2>
          <p className="text-sm text-slate-600">Latest uploads and committed datasets.</p>
        </div>
        <Link to="/ingestion" className="inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-blue-700">
          New upload
        </Link>
      </div>
      {isLoading ? <p>Loading...</p> : <DataTable data={data} columns={columns} />}
    </Card>
  )
}
