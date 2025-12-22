import { useAuth } from '../../auth/useAuth'
import { Button } from '../../components/ui/button'
import { formatDate } from '../../utils/date'

export function Topbar({ title }: { title?: string }) {
  const { user, logout } = useAuth()
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{title || 'Dashboard'}</h1>
        <p className="text-xs text-slate-500">Tenant: {user?.tenant_id || '-'} · Role: {user?.role || '-'}</p>
      </div>
      <div className="flex items-center gap-3 text-sm text-slate-600">
        <span>Last refresh {formatDate(Date.now())}</span>
        <Button variant="ghost" onClick={logout}>
          Logout
        </Button>
      </div>
    </header>
  )
}
