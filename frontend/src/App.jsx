import React from 'react'
import UploadPage from './pages/UploadPage'
import ValidationPage from './pages/ValidationPage'
import ExceptionsPage from './pages/ExceptionsPage'
import AccumulationPage from './pages/AccumulationPage'
import ThresholdsPage from './pages/ThresholdsPage'
import DriftPage from './pages/DriftPage'
import GovernancePage from './pages/GovernancePage'
import AuditLogPage from './pages/AuditLogPage'

export default function App() {
  return (
    <main style={{ fontFamily: 'sans-serif', padding: '1rem', lineHeight: 1.5 }}>
      <header>
        <h1>Aegis Climate Control Tower</h1>
        <p>Minimal MVP UI covering ingestion, analytics, and governance workflows.</p>
      </header>
      <UploadPage />
      <ValidationPage />
      <ExceptionsPage />
      <AccumulationPage />
      <ThresholdsPage />
      <DriftPage />
      <GovernancePage />
      <AuditLogPage />
    </main>
  )
}
