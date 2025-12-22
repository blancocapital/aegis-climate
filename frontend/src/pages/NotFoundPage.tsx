import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-slate-100 p-6 text-center">
      <h1 className="text-2xl font-semibold text-slate-900">Page not found</h1>
      <p className="text-sm text-slate-600">The page you requested doesn&apos;t exist.</p>
      <Link className="text-sm font-medium text-blue-600 hover:underline" to="/">
        Go back home
      </Link>
    </div>
  )
}
