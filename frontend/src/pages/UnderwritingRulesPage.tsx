import { useMemo, useState } from 'react'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
import { Button } from '../components/ui/button'
import { Textarea } from '../components/ui/textarea'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'
import { useCreateUWRule, useUWRules } from '../api/hooks'
import { UWRule } from '../api/types'

const targets = ['LOCATION', 'ROLLUP']
const categories = ['APPETITE', 'REFERRAL', 'CONDITION', 'DECLINE']
const severities = ['INFO', 'WARN', 'CRITICAL']
const dispositions = ['NONE', 'REFER', 'CONDITION', 'DECLINE']
const logicOptions = [
  { value: 'all', label: 'ALL (AND)' },
  { value: 'any', label: 'ANY (OR)' },
]
const operators = ['==', '!=', '>', '>=', '<', '<=', 'in', 'not_in', 'exists']

const fieldOptions = [
  { value: 'tiv', label: 'TIV' },
  { value: 'country', label: 'Country' },
  { value: 'state_region', label: 'State/Region' },
  { value: 'postal_code', label: 'Postal code' },
  { value: 'lob', label: 'LOB' },
  { value: 'product_code', label: 'Product code' },
  { value: 'currency', label: 'Currency' },
  { value: 'quality_tier', label: 'Quality tier' },
  { value: 'geocode_confidence', label: 'Geocode confidence' },
  { value: 'hazard_band', label: 'Hazard band' },
  { value: 'hazard_category', label: 'Hazard category' },
  { value: 'rollup.metrics.tiv_sum', label: 'Rollup TIV sum' },
  { value: 'rollup.metrics.location_count', label: 'Rollup location count' },
]

interface PredicateRow {
  field: string
  op: string
  value: string
}

export function UnderwritingRulesPage() {
  const { data: rules = [], refetch } = useUWRules()
  const createRule = useCreateUWRule()
  const [name, setName] = useState('')
  const [target, setTarget] = useState(targets[0])
  const [category, setCategory] = useState(categories[0])
  const [severity, setSeverity] = useState(severities[1])
  const [logic, setLogic] = useState('all')
  const [disposition, setDisposition] = useState('REFER')
  const [conditions, setConditions] = useState('Confirm COPE data')
  const [predicates, setPredicates] = useState<PredicateRow[]>([
    { field: fieldOptions[0].value, op: '>=', value: '1000000' },
  ])
  const [active, setActive] = useState(true)

  const ruleJson = useMemo(() => {
    const when = {
      [logic]: predicates
        .filter((p) => p.field && p.op)
        .map((p) => {
          if (p.op === 'exists') {
            return { field: p.field, op: p.op }
          }
          const rawValue = p.value.trim()
          const value =
            ['in', 'not_in'].includes(p.op) && rawValue
              ? rawValue.split(',').map((val) => val.trim()).filter(Boolean)
              : rawValue
          return { field: p.field, op: p.op, value }
        }),
    }
    return {
      when,
      then: {
        disposition,
        suggested_conditions: conditions
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean),
      },
    }
  }, [logic, predicates, disposition, conditions])

  const addPredicate = () => {
    setPredicates((prev) => [...prev, { field: fieldOptions[0].value, op: '==', value: '' }])
  }

  const updatePredicate = (idx: number, patch: Partial<PredicateRow>) => {
    setPredicates((prev) => prev.map((row, i) => (i === idx ? { ...row, ...patch } : row)))
  }

  const removePredicate = (idx: number) => {
    setPredicates((prev) => prev.filter((_, i) => i !== idx))
  }

  const submitRule = async () => {
    if (!name.trim()) return
    await createRule.mutateAsync({
      name: name.trim(),
      category,
      severity,
      target,
      active,
      rule_json: ruleJson,
    })
    setName('')
    refetch()
  }

  const columns: ColumnDef<UWRule>[] = [
    { header: 'Name', accessorKey: 'name' },
    { header: 'Category', accessorKey: 'category' },
    { header: 'Severity', accessorKey: 'severity' },
    { header: 'Target', accessorKey: 'target' },
    { header: 'Active', accessorKey: 'active', cell: ({ getValue }) => (getValue() ? 'Yes' : 'No') },
    { header: 'Rule JSON', accessorKey: 'rule_json', cell: ({ getValue }) => <pre className="text-xs">{JSON.stringify(getValue(), null, 2)}</pre> },
  ]

  return (
    <div className="space-y-4">
      <Card className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Appetite & referral rules</h2>
          <p className="text-sm text-slate-600">Build deterministic rules with a safe DSL.</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <Input placeholder="Rule name" value={name} onChange={(e) => setName(e.target.value)} />
          <Select value={target} onChange={(e) => setTarget(e.target.value)}>
            {targets.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
          <Select value={category} onChange={(e) => setCategory(e.target.value)}>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <Select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            {severities.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
          <Select value={active ? 'true' : 'false'} onChange={(e) => setActive(e.target.value === 'true')}>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </Select>
          <Select value={logic} onChange={(e) => setLogic(e.target.value)}>
            {logicOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
          <Select value={disposition} onChange={(e) => setDisposition(e.target.value)}>
            {dispositions.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-2">
          <div className="text-sm font-medium">Conditions</div>
          <Textarea value={conditions} onChange={(e) => setConditions(e.target.value)} />
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium">Predicates</div>
            <Button variant="ghost" onClick={addPredicate}>
              Add predicate
            </Button>
          </div>
          {predicates.map((row, idx) => (
            <div key={`${row.field}-${idx}`} className="grid gap-2 md:grid-cols-[2fr,1fr,2fr,auto]">
              <Select value={row.field} onChange={(e) => updatePredicate(idx, { field: e.target.value })}>
                {fieldOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
              <Select value={row.op} onChange={(e) => updatePredicate(idx, { op: e.target.value })}>
                {operators.map((op) => (
                  <option key={op} value={op}>
                    {op}
                  </option>
                ))}
              </Select>
              {row.op === 'exists' ? (
                <Input placeholder="(no value)" disabled />
              ) : (
                <Input
                  placeholder="Value (comma separated for lists)"
                  value={row.value}
                  onChange={(e) => updatePredicate(idx, { value: e.target.value })}
                />
              )}
              <Button variant="ghost" onClick={() => removePredicate(idx)}>
                Remove
              </Button>
            </div>
          ))}
        </div>
        <div className="space-y-2">
          <div className="text-sm font-medium">JSON preview</div>
          <pre className="rounded-md bg-slate-50 p-3 text-xs">{JSON.stringify(ruleJson, null, 2)}</pre>
        </div>
        <Button onClick={submitRule} disabled={!name.trim() || createRule.isPending}>
          {createRule.isPending ? 'Saving...' : 'Create rule'}
        </Button>
      </Card>

      <Card className="space-y-3">
        <h3 className="text-lg font-semibold">Existing rules</h3>
        {rules.length ? <DataTable data={rules} columns={columns} /> : <p className="text-sm text-slate-600">No rules yet.</p>}
      </Card>
    </div>
  )
}
