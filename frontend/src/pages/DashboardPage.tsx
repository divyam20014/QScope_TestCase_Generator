import { Card, CardContent } from '@/components/ui/card'
import { api } from '@/lib/api'
import type { Project } from '@/types/project'
import { useQuery } from '@tanstack/react-query'
import { FileText, FlaskConical, ListChecks, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

function Kpi({
  icon: Icon,
  label,
  value,
  to,
}: {
  icon: typeof FlaskConical
  label: string
  value: number
  to: string
}) {
  return (
    <Link to={to}>
      <Card className="transition-colors hover:border-[var(--color-accent)]">
        <CardContent className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-[var(--color-accent)]/10 text-[var(--color-accent)]">
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <div className="text-2xl font-semibold text-[var(--color-text)]">{value}</div>
            <div className="text-xs text-[var(--color-text-muted)]">{label}</div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

export function DashboardPage() {
  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<Project[]>('/projects'),
  })

  const totals = (projects ?? []).reduce(
    (acc, p: Project) => ({
      documents: acc.documents + p.document_count,
      requirements: acc.requirements + p.requirement_count,
      testCases: acc.testCases + p.test_case_count,
    }),
    { documents: 0, requirements: 0, testCases: 0 },
  )

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">Dashboard</h1>

      {isLoading && <p className="text-sm text-[var(--color-text-muted)]">Loading...</p>}

      {!isLoading && (
        <>
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi icon={FlaskConical} label="Projects" value={projects?.length ?? 0} to="/projects" />
            <Kpi icon={FileText} label="Documents" value={totals.documents} to="/documents" />
            <Kpi
              icon={ListChecks}
              label="Requirements"
              value={totals.requirements}
              to="/requirement-analysis"
            />
            <Kpi icon={Sparkles} label="Test Cases" value={totals.testCases} to="/test-repository" />
          </div>

          {(projects ?? []).length === 0 && (
            <Card>
              <CardContent className="py-10 text-center text-sm text-[var(--color-text-muted)]">
                No projects yet.{' '}
                <Link to="/projects" className="text-[var(--color-accent)] underline">
                  Create your first project
                </Link>{' '}
                to start uploading requirement documents and generating test cases.
              </CardContent>
            </Card>
          )}

          <p className="mt-6 text-xs text-[var(--color-text-muted)]">
            Category distribution, coverage and module-wise charts will populate here once document
            analysis and test generation (Phases 2-7) are implemented.
          </p>
        </>
      )}
    </div>
  )
}
