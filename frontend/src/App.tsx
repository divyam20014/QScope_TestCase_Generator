import { AppLayout } from '@/components/layout/AppLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { DocumentsPage } from '@/pages/DocumentsPage'
import { PlaceholderPage } from '@/pages/PlaceholderPage'
import { ProjectsPage } from '@/pages/ProjectsPage'
import { Route, Routes } from 'react-router-dom'

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route
          path="/requirement-analysis"
          element={<PlaceholderPage title="Requirement Analysis" phase="Phase 5" />}
        />
        <Route
          path="/test-generator"
          element={<PlaceholderPage title="Test Case Generator" phase="Phase 6" />}
        />
        <Route
          path="/test-repository"
          element={<PlaceholderPage title="Test Case Repository" phase="Phase 8" />}
        />
        <Route
          path="/coverage"
          element={<PlaceholderPage title="Coverage Analysis" phase="Phase 7" />}
        />
        <Route path="/reports" element={<PlaceholderPage title="Reports" phase="Phase 9" />} />
        <Route
          path="/ai-configuration"
          element={<PlaceholderPage title="AI Configuration" phase="Phase 4 (Gemini Integration)" />}
        />
        <Route path="/settings" element={<PlaceholderPage title="Settings" phase="a later phase" />} />
      </Routes>
    </AppLayout>
  )
}
