import { AppLayout } from '@/components/layout/AppLayout'
import { AIConfigurationPage } from '@/pages/AIConfigurationPage'
import { CoverageAnalysisPage } from '@/pages/CoverageAnalysisPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { DocumentsPage } from '@/pages/DocumentsPage'
import { PlaceholderPage } from '@/pages/PlaceholderPage'
import { ProjectsPage } from '@/pages/ProjectsPage'
import { ReportsPage } from '@/pages/ReportsPage'
import { RepositoryPage } from '@/pages/RepositoryPage'
import { RequirementAnalysisPage } from '@/pages/RequirementAnalysisPage'
import { TestGeneratorPage } from '@/pages/TestGeneratorPage'
import { Route, Routes } from 'react-router-dom'

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/requirement-analysis" element={<RequirementAnalysisPage />} />
        <Route path="/test-generator" element={<TestGeneratorPage />} />
        <Route path="/test-repository" element={<RepositoryPage />} />
        <Route path="/coverage" element={<CoverageAnalysisPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/ai-configuration" element={<AIConfigurationPage />} />
        <Route path="/settings" element={<PlaceholderPage title="Settings" phase="a later phase" />} />
      </Routes>
    </AppLayout>
  )
}
