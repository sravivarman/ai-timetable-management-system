# Administrative Reports & Export Framework

The Reports workspace contains two complementary concepts:

- **Operational reports** render timetable grids, utilization, free resources, validation, solver, and conflict data.
- **Administrative reports** are configurable tabular reports with a server-authorized preview and full-dataset exports.

Master Data CSV exports remain import/data-maintenance files. Administrative report exports are human-facing documents and do not replace them.

## Registered reports

The reusable registry defines Faculty Master, Course Offerings, Theory Faculty Allocations, Activity Faculty Allocations, Section-wise Course & Faculty Allocation, Faculty Workload, Semester Session Progress, Slot Session Progress, Slot Requirement Completeness, Slot Faculty Workload, and the actual-date Slot Timetable.

For each report, the backend definition declares its allowed and default columns, filter metadata, sortable columns, default ordering, formats, description, and layout type. The shared column registry supplies stable labels, data types, widths, alignment, and formatting semantics. A report is added by registering its definition and canonical data provider; exporters do not contain report-specific queries.

## User workflow

1. Select an administrative report.
2. Choose readable filters. Filters do not need to be output columns.
3. select, clear, or restore default columns.
4. Arrange selected columns with keyboard-accessible Move Up/Move Down controls.
5. Configure independent multi-column sorting.
6. Preview the paginated canonical result.
7. Export the complete filtered result to Excel, CSV, Word, or PDF.

Changing configuration marks an existing preview as stale. Export always submits the current validated configuration and regenerates the authorized dataset on the server.

## API

- `GET /api/v1/reports/definitions`
- `POST /api/v1/reports/preview`
- `POST /api/v1/reports/export?format=xlsx|csv|docx|pdf`

All endpoints require `reports.read`. Report keys, filters, columns, and sort keys are allow-listed. Requests cannot supply SQL or database column expressions. UUIDs remain internal filter values; previews and exports contain readable business values.

Preview and all four renderers consume the same canonical result. CSV is UTF-8 raw tabular data. Excel includes an administrative heading, filter context, typed cells, widths, frozen headings, and autofilter. Word and PDF include a generic application heading, filter summary, repeated table headers, and automatic landscape layout for wide selections. Files are generated in memory.

Faculty Workload uses `configured_faculty_workloads`, the existing authoritative weekly planned-workload source. It separately invokes that service for ordinary and activity offering sets, then displays their sum; no report-only workload formula is introduced. Slot Faculty Workload is intentionally separate: it reports actual Slot periods and completed sessions plus per-day averages, with weekly minimum and maximum values shown only as reference limits.

Semester and Slot progress use the central session-counting service. It counts a multi-period class as one session, requires complete Student Group coverage for grouped activities, accounts for rotation/combined occurrences per offering, and avoids summing historical timetable versions. Approval and publication transitions capture immutable progress snapshots. The Slot Timetable dataset is long-form and uses actual dates with readable Section, Course, Faculty, Classroom, Laboratory, and Student Group values.

Report definitions and temporary page configuration are code/client-state driven. Migration `0036` supplies Semester Requirements and immutable workflow progress snapshots used by the new report providers. Slot Timetable exports use the canonical long-form dataset for CSV, a matrix plus detail sheet for Excel, and landscape timetable matrices for Word/PDF. Saved report views, scheduling, subscriptions, formulas, and charts remain future extensions.
