import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'
import App from './App'
import { LoginPage } from '../pages/LoginPage'
import { RequireAuth } from '../auth/RequireAuth'
import { IngestionWizardPage } from '../pages/IngestionWizardPage'
import { ExposureVersionsPage } from '../pages/ExposureVersionsPage'
import { ExposureVersionDetailPage } from '../pages/ExposureVersionDetailPage'
import { ExceptionsPage } from '../pages/ExceptionsPage'
import { HazardDatasetsPage } from '../pages/HazardDatasetsPage'
import { OverlaysPage } from '../pages/OverlaysPage'
import { RollupsPage } from '../pages/RollupsPage'
import { ThresholdRulesPage } from '../pages/ThresholdRulesPage'
import { BreachesPage } from '../pages/BreachesPage'
import { RunsPage } from '../pages/RunsPage'
import { AuditLogPage } from '../pages/AuditLogPage'
import { AuthProvider } from '../auth/AuthProvider'
import { NotFoundPage } from '../pages/NotFoundPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <AuthProvider>
        <Outlet />
      </AuthProvider>
    ),
    children: [
      { path: 'login', element: <LoginPage /> },
      { path: '*', element: <NotFoundPage /> },
      {
        element: (
          <RequireAuth>
            <App />
          </RequireAuth>
        ),
        children: [
          { index: true, element: <Navigate to="/ingestion" /> },
          { path: 'ingestion', element: <IngestionWizardPage /> },
          { path: 'exposure-versions', element: <ExposureVersionsPage /> },
          { path: 'exposure-versions/:id', element: <ExposureVersionDetailPage /> },
          { path: 'exceptions', element: <ExceptionsPage /> },
          { path: 'hazard-datasets', element: <HazardDatasetsPage /> },
          { path: 'overlays', element: <OverlaysPage /> },
          { path: 'rollups', element: <RollupsPage /> },
          { path: 'threshold-rules', element: <ThresholdRulesPage /> },
          { path: 'breaches', element: <BreachesPage /> },
          { path: 'runs', element: <RunsPage /> },
          { path: 'audit-log', element: <AuditLogPage /> },
        ],
      },
    ],
  },
])
