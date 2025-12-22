import React from 'react'
import { cn } from './utils'

export function Table({ children, className }: { children: React.ReactNode; className?: string }) {
  return <table className={cn('min-w-full text-sm text-left', className)}>{children}</table>
}

export function THead({ children }: { children: React.ReactNode }) {
  return <thead className="bg-slate-100 text-xs uppercase text-slate-600">{children}</thead>
}

export function TBody({ children }: { children: React.ReactNode }) {
  return <tbody className="divide-y divide-slate-200 bg-white">{children}</tbody>
}

export function TR({ children }: { children: React.ReactNode }) {
  return <tr className="hover:bg-slate-50">{children}</tr>
}

export function TH({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={cn('px-4 py-2 font-semibold', className)}>{children}</th>
}

export function TD({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cn('px-4 py-2 align-top', className)}>{children}</td>
}
