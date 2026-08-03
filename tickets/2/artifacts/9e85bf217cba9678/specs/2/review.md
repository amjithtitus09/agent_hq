# Review: Support for creating multiple diagnostic reports for SR

## Round 1

- **blocker** `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx:250` — observations upsert uses `latestReport?.id` instead of selected report ID, breaking multi-report workflow.
- **blocker** `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx:174-180` — all reports queried unconditionally with `useQuery` in a loop; use conditional hook pattern or memoize query array.
- **should-fix** `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx:140-144` — `selectedReportId` initialization effect runs on every render when `latestReport` exists; add dependency to prevent re-initialization.
