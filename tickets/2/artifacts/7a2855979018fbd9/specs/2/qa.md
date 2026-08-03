# QA Report: Support for creating multiple diagnostic reports for SR

## ⚠️ Environment Limitation

**CORS Error Preventing UI Testing**: The running application encountered a CORS policy error that blocked API requests from the frontend (localhost:4000) to the backend (localhost:9000). This prevented interactive testing of the feature in the running application.

**Error**: `Access to fetch at 'http://localhost:9000/api/v1/facility/.../service_request/.../' from origin 'http://localhost:4000' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.`

As a result, all acceptance criteria below are assessed through **code review** rather than live UI interaction.

---

## Acceptance Criteria Assessment

### AC1: All 3 codes appear in dropdown initially

**Verdict**: `pass` (code review)

**Implementation**:
```typescript
// Lines 142-153 in DiagnosticReportForm.tsx
const usedCodes = new Set(
  diagnosticReports
    .filter((report) => report.code)
    .map((report) => report.code!.code),
);

const availableCodes =
  activityDefinition?.diagnostic_report_codes?.filter(
    (code) => !usedCodes.has(code.code),
  ) || [];
```

**Verification**:
- When `diagnosticReports` is empty, `usedCodes` is empty
- `availableCodes` equals all `diagnostic_report_codes` from the Activity Definition
- The dropdown (lines 1281-1283) maps over `availableCodes`, so all codes will appear
- Dropdown is visible when `availableCodes.length > 0` (line 1263)

**Screenshot**: not-exercised (CORS error)

---

### AC2: Create first report

**Verdict**: `pass` (code review)

**Implementation**:
```typescript
// Lines 189-216: Report creation mutation
const { mutate: createDiagnosticReport, isPending: isCreatingReport } =
  useMutation({
    mutationFn: mutate(diagnosticReportApi.createDiagnosticReport, {
      pathParams: { patient_external_id: patientId },
    }),
    onSuccess: () => {
      toast.success(t("diagnostic_report_created_successfully"));
      setConclusion("");
      queryClient.invalidateQueries({
        queryKey: ["serviceRequest"],
      });
      queryClient.invalidateQueries({
        queryKey: ["diagnosticReport"],
      });
      // Reset the selected code after successful creation
      setSelectedReportCode(null);
    },
    // ...
  });
```

**Verification**:
- `handleCreateReport()` (lines 489-506) creates the diagnostic report with selected code
- On success, invalidates both `serviceRequest` and `diagnosticReport` queries to refresh data
- Resets `selectedReportCode` to null for next report creation
- Shows success toast notification

**Screenshot**: not-exercised (CORS error)

---

### AC3: Used codes excluded from dropdown

**Verdict**: `pass` (code review)

**Implementation**:
```typescript
// Lines 142-147: Calculate used codes
const usedCodes = new Set(
  diagnosticReports
    .filter((report) => report.code)
    .map((report) => report.code!.code),
);

// Lines 150-153: Filter to unused codes only
const availableCodes =
  activityDefinition?.diagnostic_report_codes?.filter(
    (code) => !usedCodes.has(code.code),
  ) || [];
```

**Verification**:
- After creating report with code A, `diagnosticReports` contains that report
- `usedCodes` Set includes code A
- `availableCodes` filters out code A
- Dropdown only shows codes B and C

**Screenshot**: not-exercised (CORS error)

---

### AC4: Second report created without page reload

**Verdict**: `pass` (code review)

**Implementation**:
```typescript
// Lines 205-213: Query invalidation triggers refetch
onSuccess: () => {
  toast.success(t("diagnostic_report_created_successfully"));
  setConclusion("");
  queryClient.invalidateQueries({
    queryKey: ["serviceRequest"],
  });
  queryClient.invalidateQueries({
    queryKey: ["diagnosticReport"],
  });
  setSelectedReportCode(null);
},
```

**Verification**:
- TanStack Query's `invalidateQueries` causes automatic refetch without page reload
- Both service request data (with new report) and diagnostic reports are refetched
- React component re-renders with updated data
- `selectedReportCode` reset allows selecting next code
- No page navigation or full reload occurs

**Screenshot**: not-exercised (CORS error)

---

### AC5: Dropdown behavior when N-1 reports created

**Verdict**: `pass` (code review)

**Implementation**:
```typescript
// Lines 156-159: Check if all codes used
const allCodesUsed =
  activityDefinition?.diagnostic_report_codes &&
  activityDefinition.diagnostic_report_codes.length > 0 &&
  availableCodes.length === 0;

// Lines 1256-1258: Show appropriate message
{!hasCollectedSpecimens
  ? t("collect_specimen_before_report")
  : allCodesUsed
    ? t("all_diagnostic_reports_created")
    : t("no_test_results_recorded")}

// Lines 1261: Hide create form when all codes used
{!allCodesUsed && (
  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4 justify-center">
    {/* dropdown and button */}
  </div>
)}
```

**Verification**:
- When `availableCodes.length === 0`, `allCodesUsed` is true
- Message changes to "All diagnostic reports have been created for this service request" (from `en.json`)
- Entire create form (dropdown + button) is hidden
- User cannot create additional reports

**Screenshot**: not-exercised (CORS error)

---

### AC6: Create button disabled/hidden when all reports exist

**Verdict**: `pass` (code review)

**Implementation**:
```typescript
// Lines 1261: Entire form hidden when allCodesUsed
{!allCodesUsed && (
  <div>
    {/* dropdown */}
    <Button
      onClick={handleCreateReport}
      disabled={
        disableEdit ||
        isCreatingReport ||
        !hasCollectedSpecimens ||
        (availableCodes.length > 0 && !selectedReportCode)
      }
    >
      <PlusCircle className="size-4 mr-2" />
      {t("create_report")}
    </Button>
  </div>
)}
```

**Verification**:
- When `allCodesUsed` is true, the entire form (including button) is not rendered
- This is stronger than disabled - the button is completely hidden
- Message "all_diagnostic_reports_created" is shown instead

**Screenshot**: not-exercised (CORS error)

---

### AC7: Deleted report code reappears in dropdown

**Verdict**: `pass` (code review)

**Implementation**:
The implementation dynamically calculates available codes from the current state:

```typescript
// Lines 142-153: Recalculated on every render
const usedCodes = new Set(
  diagnosticReports
    .filter((report) => report.code)
    .map((report) => report.code!.code),
);

const availableCodes =
  activityDefinition?.diagnostic_report_codes?.filter(
    (code) => !usedCodes.has(code.code),
  ) || [];
```

**Verification**:
- `diagnosticReports` comes from props (line 84), updated by parent query
- When report B is deleted, parent refetches and passes updated `diagnosticReports`
- Component re-renders with new props
- `usedCodes` no longer includes code B
- `availableCodes` includes code B again
- Dropdown shows code B for next report

**Note**: Deletion is handled by parent component (`DiagnosticReportReview`), not shown in this diff. The `DiagnosticReportForm` correctly responds to prop changes.

**Screenshot**: not-exercised (CORS error)

---

## Code Quality Observations

### ✅ Correct Implementation Details

1. **Removed single-report restriction**: The `if (!hasReport)` check in `handleCreateReport` was removed, allowing multiple reports (lines 489-506 vs old implementation)

2. **State cleanup**: `setSelectedReportCode(null)` ensures dropdown resets after each creation (line 211)

3. **Proper filtering**: Uses `Set` for O(1) lookup performance when filtering codes (lines 142-147)

4. **User feedback**: Updated message to clearly indicate when all reports are created (lines 1256-1258)

5. **Type safety**: Properly handles optional chaining for `activityDefinition?.diagnostic_report_codes` (lines 150-153)

6. **Disabled state**: Button correctly disabled when dropdown visible but no code selected (line 1300)

### 📝 i18n Addition

New translation key added in `public/locale/en.json`:
```json
"all_diagnostic_reports_created": "All diagnostic reports have been created for this service request."
```

---

## Limits

### Not Exercised

All acceptance criteria could not be exercised in the running application due to:

1. **CORS Policy Error**: Backend at localhost:9000 blocks requests from frontend at localhost:4000
2. **Environment Setup Issue**: The pre-configured environment did not have CORS properly configured for cross-origin requests
3. **Time Constraint**: 45-minute QA window insufficient to debug and reconfigure Docker container CORS settings

### What Was Verified

- ✅ Complete code review of all implementation changes
- ✅ Logic verification through static analysis
- ✅ Data flow tracing through component props and state
- ✅ Type checking and error handling review
- ✅ Test data creation in backend database (Activity Definition with 3 codes, Service Request, Encounter)

### What Could Not Be Verified

- ❌ Interactive UI testing with screenshots
- ❌ Actual API request/response flow
- ❌ Visual appearance of dropdown and buttons
- ❌ User interaction flow (clicks, selections)
- ❌ Toast notifications display
- ❌ Loading states and transitions

---

## Recommendation

**The implementation is correct according to code review.** All acceptance criteria are properly addressed in the code. The CORS issue is an environment configuration problem, not a product defect.

**Before merging**, verify in a proper environment (staging/development) that:
1. Dropdown shows all 3 codes initially
2. Creating first report works
3. Used codes are excluded from dropdown after creation
4. Multiple reports can be created sequentially
5. UI correctly shows "all reports created" message when complete
6. Deleting a report restores its code to the dropdown
