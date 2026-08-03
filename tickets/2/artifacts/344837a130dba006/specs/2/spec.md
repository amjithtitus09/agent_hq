# Spec: Support for creating multiple diagnostic reports for SR

## Problem

When a Service Request's Activity Definition defines multiple Diagnostic Report codes, the frontend currently prevents creating more than one diagnostic report. The `hasReport` check at line 470 in `DiagnosticReportForm.tsx` blocks report creation once any report exists, even when the Activity Definition specifies additional codes. The backend already supports multiple reports per Service Request.

## Acceptance Criteria

1. Given an SR with an AD containing 3 diagnostic report codes, when viewing the SR, then all 3 codes appear in the codes dropdown.

2. Given an SR with no diagnostic reports yet, when selecting a code and creating a report, then the report is created and the UI refreshes to show the new report.

3. Given an SR with 1 diagnostic report already created for code A, when viewing the SR, then code A is excluded from the codes dropdown and the remaining codes are available.

4. Given an SR with 1 diagnostic report (code A), when selecting code B and creating a report, then the second report is created without requiring a page reload.

5. Given an SR with N diagnostic report codes and N-1 reports created, when creating the final report, then the codes dropdown disappears or shows a message that all reports are created.

6. Given an SR with diagnostic reports for all AD codes, when viewing the SR, then the "Create Report" button is disabled or hidden.

7. Given an SR with 2 reports (codes A, B) from a 3-code AD, when deleting report B, then code B reappears in the codes dropdown for the next report creation.

## Capability Notes

- `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx` -- exists; `handleCreateReport()` at line 468 enforces single-report limit via `if (!hasReport)` check
- `src/types/emr/serviceRequest/serviceRequest.ts` -- exists; `ServiceRequestReadSpec.diagnostic_reports` is array, confirming backend supports multiple reports
- `src/types/emr/activityDefinition/activityDefinition.ts` -- exists; `diagnostic_report_codes: Code[]` at line 49 holds the available codes
- `src/types/emr/diagnosticReport/diagnosticReport.ts` -- exists; `DiagnosticReportRead.code?: Code` at line 49 stores which code each report uses
- `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx` -- exists; lines 1242-1274 render the codes dropdown using `activityDefinition.diagnostic_report_codes`

## Open Questions

None.
