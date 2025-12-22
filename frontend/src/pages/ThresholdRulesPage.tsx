import { useState } from 'react'
import { useCreateThresholdRule, useThresholdRules } from '../api/hooks'
import { Card } from '../components/ui/card'
import { DataTable } from '../components/DataTable'
import { ColumnDef } from '@tanstack/react-table'
import { ThresholdRule } from '../api/types'
import { Input } from '../components/ui/input'
import { Button } from '../components/ui/button'
import { Textarea } from '../components/ui/textarea'

export function ThresholdRulesPage() {
  const { data: rules = [], refetch } = useThresholdRules()
  const createRule = useCreateThresholdRule()
  const [name, setName] = useState('High loss')
  const [severity, setSeverity] = useState('CRITICAL')
  const [ruleJson, setRuleJson] = useState('{"field": "tiv_sum", "op": ">", "value": 1000000}')

  const columns: ColumnDef<ThresholdRule>[] = [
    { header: 'ID', accessorKey: 'id' },
    { header: 'Name', accessorKey: 'name' },
    { header: 'Severity', accessorKey: 'severity' },
  ]

  const saveRule = async () => {
    await createRule.mutateAsync({ name, severity, rule_json: JSON.parse(ruleJson) })
    refetch()
  }

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-semibold">Threshold rules</h2>
      <div className="grid gap-2 md:grid-cols-3">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
        <Input value={severity} onChange={(e) => setSeverity(e.target.value)} placeholder="Severity" />
        <Textarea rows={3} value={ruleJson} onChange={(e) => setRuleJson(e.target.value)} />
      </div>
      <Button onClick={saveRule}>Create rule</Button>
      <DataTable data={rules} columns={columns} />
    </Card>
  )
}
