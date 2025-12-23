import React from 'react'
import { cn } from './utils'

export function Table({ children, className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <table className={cn('min-w-full text-sm text-left', className)} {...props}>
      {children}
    </table>
  )
}

export function THead({ children, className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={cn('bg-slate-100 text-xs uppercase text-slate-600', className)} {...props}>
      {children}
    </thead>
  )
}

export function TBody({ children, className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody className={cn('divide-y divide-slate-200 bg-white', className)} {...props}>
      {children}
    </tbody>
  )
}

export function TR({ children, className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={cn('hover:bg-slate-50', className)} {...props}>
      {children}
    </tr>
  )
}

export function TH({ children, className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={cn('px-4 py-2 font-semibold', className)} {...props}>
      {children}
    </th>
  )
}

export function TD({ children, className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn('px-4 py-2 align-top', className)} {...props}>
      {children}
    </td>
  )
}
