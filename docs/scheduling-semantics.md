# Scheduling quantity semantics

These definitions are authoritative for Course master data, prerequisite
validation, solver input, timetable generation, and reporting.

## Academic contact pattern

- `weekly_periods` is the number of academic contact periods received by each
  attending section or student group each week.
- `session_duration` is the number of consecutive timetable periods in one
  attendance session.
- `sessions_per_week` is the number of sessions attended by each section or
  student group each week.
- A valid Course pattern satisfies:

  `weekly_periods = session_duration × sessions_per_week`

The student-group count is deliberately absent from that equation.

`FULL_SECTION` means the section attends as one unit. `GROUPED` means each
active student group must receive the complete Course contact pattern. The
Course `default_group_count` is a reusable default; an active offering-specific
student-group configuration is the effective count used by validation and the
solver.

## Three distinct measurements

1. **Student contact periods** are measured per section/group and equal
   `weekly_periods` for a complete offering.
2. **Section timetable occupancy** is the union of periods in which any part of
   the section is scheduled. Parallel synchronized children occupy one shared
   section block, while sequential group sessions occupy separate blocks.
3. **Faculty and facility occupancy** is measured from physical occurrences.
   Before solving, configured faculty workload expands group-specific
   occurrences. After solving, timetable entries are the authoritative source
   for faculty workload and classroom/laboratory utilization.

## Synchronized activity rotations

A rotation block is one solver decision with one child entry per participating
student group. Every `(student group, course offering)` pair must appear
`sessions_per_week` times across the complete matrix. All rotating activities
must have a compatible duration and sessions-per-week pattern.

For two groups and two 3-period activities, each configured for one session per
week, the matrix contains two synchronized 3-period blocks. Each group receives
three periods of each activity, the section is occupied for six periods, and
each course retains `weekly_periods = 3`.

For two groups, a 2-period duration, and two sessions per week, each group must
receive two occurrences of every activity. The matrix therefore repeats the
cycle and `weekly_periods` remains 4.

Physical faculty workload and laboratory utilization can exceed a Course's
`weekly_periods` when the same resource serves multiple student groups. This is
expected and must never be represented by inflating Course master data.

## Course-offering laboratory selection

Course eligibility defines technical capability. An offering may narrow or
prioritize that set, but it can never expand it:

- `AUTO`: all active, ownership-compatible course-eligible laboratories; the
  course default remains a soft preference.
- `PREFERRED`: the offering laboratory is preferred, with every other eligible
  laboratory retained as a fallback.
- `RESTRICTED`: only the offering's normalized allowed-laboratory subset. Its
  members are equally preferred.
- `FIXED`: exactly the offering override laboratory.

Resource availability and collision constraints are applied after this set is
resolved. Grouped and synchronized rotations apply it independently to every
physical occurrence; they do not permanently bind a group to one room.

## Facility concurrency and capacity

Laboratory concurrency is independent of department shareability, course
eligibility, offering selection, and availability:

- `EXCLUSIVE` (the default) preserves one unrelated logical activity per
  laboratory and slot.
- `CAPACITY_SHARED` permits arbitrary simultaneous logical activities while
  their actual participant demand remains within `capacity` in every occupied
  period.
- Full-section demand is `Section.student_strength`; grouped demand is the
  stored `StudentBatch.student_count`; a Combined Teaching event contributes
  its combined strength once even though compatibility child entries exist.
- Unavailable slots have zero usable capacity. Locked and manual entries consume
  capacity.
- A configured capacity also limits one exclusive activity, although capacity
  remains optional for exclusive laboratories.

Existing laboratories remain `EXCLUSIVE`; capacity alone never enables sharing.
