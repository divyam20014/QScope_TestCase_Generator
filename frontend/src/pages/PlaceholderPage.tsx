import { Card, CardContent } from '@/components/ui/card'

export function PlaceholderPage({ title, phase }: { title: string; phase: string }) {
  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">{title}</h1>
      <Card>
        <CardContent className="py-10 text-center text-sm text-[var(--color-text-muted)]">
          {title} will be implemented in {phase}.
        </CardContent>
      </Card>
    </div>
  )
}
