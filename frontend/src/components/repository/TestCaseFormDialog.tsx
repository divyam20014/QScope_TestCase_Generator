import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Input, Textarea } from '@/components/ui/input'
import type { Requirement } from '@/types/requirement'
import type { ManualTestCaseCreate, Priority, TestCase, TestCaseUpdate, TestCategory, TestType } from '@/types/testcase'
import { useState } from 'react'

const TEST_TYPES: TestType[] = ['business', 'application', 'system', 'integration', 'e2e', 'security']
const TEST_CATEGORIES: TestCategory[] = ['positive', 'negative', 'edge', 'boundary', 'destructive']
const PRIORITIES: Priority[] = ['critical', 'high', 'medium', 'low']

interface FormState {
  requirement_id: string
  scenario_description: string
  title: string
  test_type: TestType
  test_category: TestCategory
  preconditions: string
  test_data: string
  steps: string
  expected_result: string
  priority: Priority
  assumptions: string
}

function toFormState(tc?: TestCase, defaultRequirementId?: string): FormState {
  return {
    requirement_id: tc?.requirement_id ?? defaultRequirementId ?? '',
    scenario_description: tc?.scenario_description ?? '',
    title: tc?.title ?? '',
    test_type: tc?.test_type ?? 'system',
    test_category: tc?.test_category ?? 'positive',
    preconditions: tc?.preconditions ?? '',
    test_data: tc?.test_data ?? '',
    steps: tc?.steps.join('\n') ?? '',
    expected_result: tc?.expected_result ?? '',
    priority: tc?.priority ?? 'medium',
    assumptions: tc?.assumptions ?? '',
  }
}

interface TestCaseFormDialogProps {
  open: boolean
  onClose: () => void
  requirements: Requirement[]
  testCase?: TestCase
  isSaving: boolean
  onCreate: (data: ManualTestCaseCreate) => void
  onUpdate: (data: TestCaseUpdate) => void
}

export function TestCaseFormDialog({
  open,
  onClose,
  requirements,
  testCase,
  isSaving,
  onCreate,
  onUpdate,
}: TestCaseFormDialogProps) {
  const [form, setForm] = useState<FormState>(() => toFormState(testCase, requirements[0]?.id))

  if (!open) return null

  const isEdit = !!testCase

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function handleSubmit() {
    const steps = form.steps
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean)

    if (isEdit) {
      onUpdate({
        scenario_description: form.scenario_description,
        title: form.title,
        test_type: form.test_type,
        test_category: form.test_category,
        preconditions: form.preconditions,
        test_data: form.test_data,
        steps,
        expected_result: form.expected_result,
        priority: form.priority,
        assumptions: form.assumptions || null,
      })
    } else {
      onCreate({
        requirement_id: form.requirement_id,
        scenario_description: form.scenario_description,
        title: form.title,
        test_type: form.test_type,
        test_category: form.test_category,
        preconditions: form.preconditions,
        test_data: form.test_data,
        steps,
        expected_result: form.expected_result,
        priority: form.priority,
        assumptions: form.assumptions || null,
      })
    }
  }

  const canSubmit = form.title.trim() && form.expected_result.trim() && (isEdit || form.requirement_id)

  return (
    <Dialog open={open} onClose={onClose} title={isEdit ? `Edit ${testCase?.id}` : 'Add Test Case'}>
      <div className="max-h-[70vh] space-y-3 overflow-y-auto pr-1">
        {!isEdit && (
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Requirement</label>
            <select
              className="h-10 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-sm text-[var(--color-text)]"
              value={form.requirement_id}
              onChange={(e) => update('requirement_id', e.target.value)}
            >
              <option value="" disabled>
                Select a requirement...
              </option>
              {requirements.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id} - {r.text.slice(0, 60)}
                </option>
              ))}
            </select>
          </div>
        )}

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Title</label>
          <Input value={form.title} onChange={(e) => update('title', e.target.value)} />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Scenario description</label>
          <Input value={form.scenario_description} onChange={(e) => update('scenario_description', e.target.value)} />
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Test type</label>
            <select
              className="h-10 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-sm text-[var(--color-text)]"
              value={form.test_type}
              onChange={(e) => update('test_type', e.target.value as TestType)}
            >
              {TEST_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Category</label>
            <select
              className="h-10 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-sm text-[var(--color-text)]"
              value={form.test_category}
              onChange={(e) => update('test_category', e.target.value as TestCategory)}
            >
              {TEST_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Priority</label>
            <select
              className="h-10 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-sm text-[var(--color-text)]"
              value={form.priority}
              onChange={(e) => update('priority', e.target.value as Priority)}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Preconditions</label>
          <Textarea rows={2} value={form.preconditions} onChange={(e) => update('preconditions', e.target.value)} />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Test data</label>
          <Textarea rows={2} value={form.test_data} onChange={(e) => update('test_data', e.target.value)} />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
            Test steps (one per line)
          </label>
          <Textarea rows={4} value={form.steps} onChange={(e) => update('steps', e.target.value)} />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Expected result</label>
          <Textarea rows={2} value={form.expected_result} onChange={(e) => update('expected_result', e.target.value)} />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
            Assumptions (optional)
          </label>
          <Textarea rows={2} value={form.assumptions} onChange={(e) => update('assumptions', e.target.value)} />
        </div>
      </div>

      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={!canSubmit || isSaving}>
          {isSaving ? 'Saving...' : isEdit ? 'Save changes' : 'Add test case'}
        </Button>
      </div>
    </Dialog>
  )
}
