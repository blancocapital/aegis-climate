import React from 'react'
import { cn } from './utils'

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn('card', className)}>{children}</div>
}
