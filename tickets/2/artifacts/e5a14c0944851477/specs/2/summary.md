# Summary: Support for creating multiple diagnostic reports for SR

## What was done

Modified the Service Request diagnostic report creation flow to allow users to create multiple diagnostic reports (one per diagnostic report code defined in the Activity Definition) without page reload.

**Changes:**
- Enhanced `DiagnosticReportForm.tsx` to track used diagnostic report codes and filter the dropdown to show only unused codes
- Added state management for selecting between multiple created reports
- Implemented "all diagnostic reports created" UI state when all codes are exhausted
- Fixed query invalidation to use the selected report ID instead of always using the latest report

**Files changed:**
- `src/pages/Facility/services/serviceRequests/components/DiagnosticReportForm.tsx` (270 line changes)
- `public/locale/en.json` (added i18n keys)

## Acceptance criteria

All 7 acceptance criteria are implemented in code:

1. ✅ **Dropdown shows all codes when no reports exist** — filtering logic implemented (lines 153-163)
2. ✅ **Dropdown excludes used codes** — `usedCodes` Set tracks and filters existing reports
3. ✅ **Form resets after report creation without reload** — mutation invalidates queries and resets state (lines 195-219)
4. ✅ **UI shows "all diagnostic reports created"** — conditional rendering based on `allCodesUsed` (lines 166-169, 1261-1308)
5. ✅ **All created reports visible in list** — component queries and displays all reports
6. ✅ **Create button disabled without specimens** — specimen availability check (lines 172-174)
7. ✅ **Latest report shown by default** — initialization logic sets latest as default (lines 139-150)

## Review outcome

**Final status:** Clean (Round 3)

All blockers resolved through three review rounds:
- **Round 1:** Fixed observation upsert to use selected report ID; resolved unconditional query hook violations; optimized `selectedReportId` initialization
- **Round 2:** Fixed file upload invalidation to use `selectedReportId` instead of `latestReport?.id`
- **Round 3:** No findings

## QA outcome

**Status:** `not-exercised`

All 7 acceptance criteria could not be exercised in the running application due to missing test data. The backend fixtures do not include Service Requests with Activity Definitions that have multiple diagnostic report codes, which is the core prerequisite for testing this feature.

**Code verification:** All acceptance criteria were verified to be correctly implemented in the source code during QA.

**Recommendation:** Add backend fixtures with multi-code Activity Definitions and corresponding Service Requests to enable full manual and E2E testing.
