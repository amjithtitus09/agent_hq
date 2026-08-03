# Spec: Support for creating multiple diagnostic reports for SR

## Problem

The frontend currently only allows users to create a single diagnostic report per Service Request (SR), even when the Activity Definition (AD) defines multiple diagnostic report codes. The existing code at lines 142-159 in `DiagnosticReportForm.tsx` filters out used codes, but after creating the first report, the UI doesn't refresh to enable creating additional reports. The backend already supports multiple diagnostic reports per SR.

## Acceptance Criteria

1. Given an SR with an AD containing 3 diagnostic report codes and 0 existing reports, when the user views the SR, then the dropdown shows all 3 codes available for selection.
2. Given an SR with 1 existing diagnostic report using code A from a 3-code AD, when the user views the SR, then the dropdown shows the 2 remaining codes (B and C) and excludes code A.
3. Given an SR where the user creates a diagnostic report for code A, when the report creation succeeds, then the form resets to allow creating another report without page reload.
4. Given an SR with N diagnostic report codes where N-1 reports exist, when the user creates the Nth report, then the UI displays "all diagnostic reports created" and hides the creation controls.
5. Given an SR with multiple diagnostic reports created, when the user views the SR, then all created reports are visible in the diagnostic reports list.
6. Given an SR with an AD containing diagnostic report codes, when no specimens are collected, then the "create report" button remains disabled for all codes.
7. Given an SR with multiple created diagnostic reports, when the user expands the test results section, then the latest report is shown by default and other reports are accessible.

## Capability Notes

- `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx:142-159` -- already calculates used codes and filters available codes; needs UI state management after report creation
- `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx:195-219` -- creates diagnostic report and invalidates queries; needs to support iterative creation flow
- `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx:1261-1308` -- renders dropdown and create button; needs to show multiple reports UI
- `src/types/emr/activityDefinition/activityDefinition.ts:49` -- `diagnostic_report_codes: Code[]` already supports multiple codes on AD
- `src/types/emr/serviceRequest/serviceRequest.ts:116` -- `diagnostic_reports: DiagnosticReportRead[]` already supports multiple reports on SR

## Open Questions

None.
