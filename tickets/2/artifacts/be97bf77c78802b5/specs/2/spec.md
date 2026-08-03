# Specification: Support for creating multiple diagnostic reports for SR

## Problem Statement

The frontend already supports creating multiple diagnostic reports for a Service Request (SR) when its Activity Definition (AD) defines multiple Diagnostic Report codes. The `DiagnosticReportForm` component filters used codes, shows only remaining codes in the dropdown, and allows sequential creation of reports without page reload. This ticket appears to request functionality that is already implemented.

## Acceptance Criteria

1. Given an SR whose AD defines 3 diagnostic report codes, when the user views the SR detail page, then all 3 codes appear in the diagnostic report code selector dropdown.
2. Given the user has created 1 diagnostic report, when they view the code selector, then only the 2 remaining unused codes are shown.
3. Given the user selects an available code and clicks "Create Report", when the report is created, then the code is removed from the selector and marked as used.
4. Given all N diagnostic report codes have been used, when the user views the form, then the message "all_diagnostic_reports_created" is displayed and no creation form is shown.
5. Given multiple diagnostic reports exist for an SR, when the user expands the test results section, then a dropdown allows selecting which report to view or edit.
6. Given the user creates a new report, when the creation succeeds, then the new report appears in the report selector without requiring a page reload.
7. Given specimens have not been collected, when the user attempts to create a diagnostic report, then the code selector and create button are disabled with the message "collect_specimen_before_report".

## Capability Notes

- `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx:159-163` -- filters `diagnostic_report_codes` to exclude already-used codes in `usedCodes` set
- `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx:166-169` -- calculates `allCodesUsed` flag when available codes reach zero
- `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx:1305-1366` -- renders code selector dropdown showing only `availableCodes` with create button
- `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx:938-966` -- renders report selector dropdown when multiple reports exist
- `src/types/emr/activityDefinition/activityDefinition.ts:49` -- `diagnostic_report_codes: Code[]` exists on ActivityDefinition type

## Open Questions

None.

## Recommendation

The requested functionality is already fully implemented in the current codebase. The `DiagnosticReportForm` component correctly:
- Tracks used diagnostic report codes
- Filters the dropdown to show only remaining codes
- Allows creating multiple reports sequentially
- Updates the UI without page reload
- Shows appropriate messages when all codes are used

This ticket should be closed as already complete unless there is a specific bug or edge case not covered in the acceptance criteria above.
