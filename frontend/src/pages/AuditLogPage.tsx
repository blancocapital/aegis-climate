import { useAuditEvents } from '../api/hooks'
import { Card } from '../components/ui/card'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'
import { AuditEvent } from '../api/types'
import { formatDate } from '../utils/date'
import { Badge } from '../components/ui/badge'

export function AuditLogPage() {
  const { data = [] } = useAuditEvents()

  const columns: ColumnDef<AuditEvent>[] = [
    { header: 'ID', accessorKey: 'id' },
    { header: 'Action', accessorKey: 'action', cell: ({ getValue }) => <Badge>{String(getValue())}</Badge> },
    { header: 'Created', accessorKey: 'created_at', cell: ({ getValue }) => formatDate(getValue() as string) },
  ]

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-semibold">Audit log</h2>
      <DataTable data={data} columns={columns} />
    </Card>
  )
}
