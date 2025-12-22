import React from 'react'
import { cn } from './utils'

export function Badge({ children, className, tone = 'default' }: { children: React.ReactNode; className?: string; tone?: 'default' | 'success' | 'warn' | 'danger' }) {
  const variants: Record<string, string> = {
    default: 'bg-slate-100 text-slate-800',
    success: 'bg-green-100 text-green-700',
    warn: 'bg-amber-100 text-amber-800',
    danger: 'bg-red-100 text-red-700',
  }
  return <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium', variants[tone], className)}>{children}</span>
}
