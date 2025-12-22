import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

export function AppShell({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-slate-100">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Topbar title={title} />
        <main className="flex-1 space-y-4 p-6">{children}</main>
      </div>
    </div>
  )
}
