"use client";

import { useEffect, useState } from "react";
import { SearchableSelect } from "@/components/searchable-select";
import { Modal } from "@/components/ui";
import type { MasterConfig, MasterField } from "@/lib/master-data-config";
import type { MasterRecord } from "@/lib/master-data-api";
import { readableRecordLabel } from "@/lib/readable-labels";
import { isLaboratoryCapableCourse, normalizeOfferingLaboratoryPayload } from "@/lib/course-offering-laboratories";

type FormValue = string | boolean | string[];

export function MasterRecordForm({ config, initial, lookupRecords, mode, busy, onClose, onSubmit }: { config: MasterConfig; initial?: MasterRecord; lookupRecords: Record<string, MasterRecord[]>; mode: "create" | "edit" | "duplicate" | "bulk"; busy: boolean; onClose(): void; onSubmit(payload: Record<string, unknown>): void }) {
  const [values, setValues] = useState<Record<string, FormValue>>(() => initialValues(config, initial, mode));
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const dirty = touched.size > 0;
  useEffect(() => { const warn = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); }; window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, [dirty]);
  const close = () => { if (!dirty || window.confirm("Discard unsaved changes?")) onClose(); };
  const update = (field: MasterField, value: FormValue) => { setValues((current) => {
    const next = { ...current, [field.name]: value };
    if (config.slug === "courses" && field.name === "eligible_laboratory_ids" && Array.isArray(value) && !value.includes(String(current.default_laboratory_id ?? ""))) next.default_laboratory_id = "";
    if (config.slug === "course-offerings" && field.name === "laboratory_selection_mode" && value === "AUTO") next.laboratory_override_id = "";
    if (config.slug === "course-offerings" && field.name === "course_id") { next.laboratory_override_id = ""; next.laboratory_selection_mode = "AUTO"; }
    return next;
  }); setTouched((current) => new Set(current).add(field.name)); setErrors((current) => ({ ...current, [field.name]: "" })); };
  const submit = () => { const next = validate(config, values, mode === "bulk" ? touched : undefined, lookupRecords); setErrors(next); if (!Object.keys(next).length) onSubmit(toPayload(config, values, mode === "bulk" ? touched : undefined, lookupRecords)); };
  const title = mode === "edit" ? `Edit ${config.singular}` : mode === "duplicate" ? `Duplicate ${config.singular}` : mode === "bulk" ? `Bulk update ${config.label}` : `Add ${config.singular}`;
  return <Modal title={title} onClose={close} wide footer={<><button className="button-secondary" disabled={busy} onClick={() => { setValues(initialValues(config, initial, mode)); setTouched(new Set()); setErrors({}); }}>Reset</button><button className="button-secondary" disabled={busy} onClick={close}>Cancel</button><button className="button-primary" disabled={busy || (mode === "bulk" && !touched.size)} onClick={submit}>{busy ? "Saving…" : mode === "bulk" ? "Update selected" : "Save"}</button></>}>
    <form className="grid gap-4 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); submit(); }}>
      {config.fields.filter((field) => isFormVisible(config, field, values, lookupRecords)).map((field) => {
        let renderedField = schedulingSemanticsField(config, field);
        if (config.slug === "course-offerings" && field.name === "laboratory_override_id") renderedField = { ...renderedField, label: values.laboratory_selection_mode === "FIXED" ? "Required Laboratory" : "Preferred Laboratory" };
        return <FormField key={field.name} field={renderedField} value={values[field.name]} error={errors[field.name]} lookupRecords={filteredLookups(config, field, values, lookupRecords)} partial={mode === "bulk"} onChange={(value) => update(field, value)} />;
      })}
      {config.slug === "combined-teaching-groups" && <CombinedTeachingSummary values={values} lookupRecords={lookupRecords} />}
      {Object.keys(errors).length > 0 && <p role="alert" className="sm:col-span-2 text-sm text-red-700">Correct the highlighted fields before saving.</p>}
    </form>
  </Modal>;
}

function schedulingSemanticsField(config: MasterConfig, field: MasterField): MasterField {
  const courseHelp: Record<string, string> = {
    weekly_periods: "Number of academic periods each student or student group receives for this course per week.",
    session_duration: "Number of consecutive timetable periods in one attendance session.",
    sessions_per_week: "Number of sessions each student or student group attends for this course each week.",
    default_group_count: "Default number of student groups for grouped offerings. This controls physical scheduling multiplicity, not weekly periods.",
  };
  if (config.slug === "courses" && courseHelp[field.name]) return { ...field, helpText: courseHelp[field.name] };
  if (config.slug === "course-offerings" && field.name === "weekly_periods_override") return { ...field, helpText: "Overrides the per-student/group academic contact periods; it is never multiplied by the student-group count." };
  if (config.slug === "batch-configurations" && field.name === "number_of_groups") return { ...field, helpText: "Number of groups into which the section is divided for this activity. Each group receives the configured course sessions." };
  return field;
}

function FormField({ field, value, error, lookupRecords, partial, onChange }: { field: MasterField; value: FormValue | undefined; error?: string; lookupRecords: Record<string, MasterRecord[]>; partial: boolean; onChange(value: FormValue): void }) {
  const [lookupSearch, setLookupSearch] = useState("");
  const required = field.required && !partial; const label = `${field.label}${required ? " *" : ""}`;
  const help = field.helpText && <p className="mt-1 text-xs text-slate-500">{field.helpText}</p>;
  if (field.lookup && field.type === "multiselect") { const allRecords = lookupRecords[field.lookup.endpoint] ?? []; const records = allRecords.filter((row) => readableRecordLabel(field.lookup!.endpoint, row).toLowerCase().includes(lookupSearch.toLowerCase())); const selected = Array.isArray(value) ? value : []; return <fieldset className="sm:col-span-2"><legend className="label">{label}</legend><input className="field mb-2" aria-label={`Search ${field.label}`} placeholder={`Search ${field.label.toLowerCase()}…`} value={lookupSearch} onChange={(event) => setLookupSearch(event.target.value)} /><div className="max-h-64 space-y-2 overflow-y-auto rounded-lg border p-3 dark:border-slate-700">{records.map((row) => { const identifier = String(row[field.lookup!.valueKey ?? "id"]); const optionLabel = field.lookup!.labelKeys.map((key) => row[key]).filter(Boolean).join(" · ") || readableRecordLabel(field.lookup!.endpoint, row); return <label key={identifier} className="flex items-start gap-2 rounded p-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800"><input className="mt-0.5" type="checkbox" checked={selected.includes(identifier)} onChange={(event) => onChange(event.target.checked ? [...selected, identifier] : selected.filter((item) => item !== identifier))} /><span>{optionLabel}</span></label>; })}{!records.length && <p className="text-sm text-slate-500">{allRecords.length ? "No matching options." : `No ${field.label.toLowerCase()} are available.`}</p>}</div>{help}{error && <p className="mt-1 text-xs text-red-700">{error}</p>}</fieldset>; }
  if (field.lookup) { const options = (lookupRecords[field.lookup.endpoint] ?? []).map((row) => ({ value: String(row[field.lookup!.valueKey ?? "id"]), label: field.lookup!.labelKeys.map((key) => row[key]).filter(Boolean).join(" · ") || readableRecordLabel(field.lookup!.endpoint, row) })); return <div><SearchableSelect label={label} value={String(value ?? "")} options={options} onChange={onChange} emptyMessage={`No ${field.label.toLowerCase()} options available`} />{help}{error && <p className="mt-1 text-xs text-red-700">{error}</p>}</div>; }
  if (field.type === "boolean") return <label className="mt-6 flex items-start gap-2 rounded-lg border p-3 dark:border-slate-700"><input className="mt-0.5" type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} /><span><span className="block text-sm font-medium">{field.label}</span>{field.helpText && <span className="mt-1 block text-xs font-normal text-slate-500">{field.helpText}</span>}</span></label>;
  if (field.name === "availability_mode") { const labels: Record<string, string> = { ALL_PERIODS: "Available all instructional periods", EXCEPT_BLOCKED: "Available except blocked periods", ONLY_SELECTED: "Available only during selected periods" }; return <fieldset className="sm:col-span-2"><legend className="label">{label}</legend><div className="grid gap-2 rounded-lg border p-3 dark:border-slate-700">{field.options?.map((option) => <label key={option} className="flex items-center gap-2 text-sm"><input type="radio" name="availability_mode" value={option} checked={value === option} onChange={() => onChange(option)} />{labels[option] ?? option.replaceAll("_", " ")}</label>)}</div>{error && <p className="mt-1 text-xs text-red-700">{error}</p>}</fieldset>; }
  if (field.type === "multiselect") return <fieldset><legend className="label">{label}</legend><div className="grid grid-cols-2 gap-2 rounded-lg border p-3 dark:border-slate-700">{field.options?.map((option) => <label key={option} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Array.isArray(value) && value.includes(option)} onChange={(event) => { const current = Array.isArray(value) ? value : []; onChange(event.target.checked ? [...current, option] : current.filter((item) => item !== option)); }} />{option}</label>)}</div>{error && <p className="mt-1 text-xs text-red-700">{error}</p>}</fieldset>;
  if (field.name === "laboratory_selection_mode") return <fieldset><legend className="label">{label}</legend><div className="space-y-2 rounded-lg border p-3 dark:border-slate-700">{(["AUTO", "PREFERRED", "FIXED"] as const).map((option) => <label key={option} className="flex items-start gap-2 text-sm"><input type="radio" name={field.name} value={option} checked={value === option} onChange={() => onChange(option)} /><span><strong>{option === "AUTO" ? "Automatic selection" : option === "PREFERRED" ? "Prefer a laboratory" : "Require a laboratory"}</strong><span className="block text-xs text-slate-500">{option === "AUTO" ? "The solver may use any eligible laboratory." : option === "PREFERRED" ? "The solver prefers this laboratory but may use another eligible one." : "The solver must use the selected laboratory."}</span></span></label>)}</div>{help}{error && <p className="mt-1 text-xs text-red-700">{error}</p>}</fieldset>;
  return <label><span className="label">{label}</span>{field.type === "select" ? <select className="field" aria-invalid={Boolean(error)} value={String(value ?? "")} onChange={(event) => onChange(event.target.value)}><option value="">Select {field.label.toLowerCase()}</option>{field.options?.map((option) => <option key={option} value={option}>{option.replaceAll("_", " ")}</option>)}</select> : <input className="field" aria-invalid={Boolean(error)} type={field.type ?? "text"} min={field.min} max={field.max} placeholder={partial ? "Leave unchanged" : field.placeholder} value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} />}{help}{error && <p className="mt-1 text-xs text-red-700">{error}</p>}</label>;
}

function isVisible(field: MasterField, values: Record<string, FormValue>) { return !field.visibleWhen || field.visibleWhen.values.includes(String(values[field.visibleWhen.field] ?? "")); }
function isFormVisible(config: MasterConfig, field: MasterField, values: Record<string, FormValue>, lookups: Record<string, MasterRecord[]>) {
  if (!isVisible(field, values)) return false;
  if (config.slug === "course-offerings" && ["laboratory_selection_mode", "laboratory_override_id"].includes(field.name)) {
    const course = (lookups["/courses"] ?? []).find((row) => row.id === String(values.course_id ?? ""));
    return isLaboratoryCapableCourse(course);
  }
  return true;
}
function initialValues(config: MasterConfig, initial?: MasterRecord, mode?: string): Record<string, FormValue> { const trueDefaults = new Set(["is_shareable", "is_shareable_across_departments", "is_available_all_periods", "is_working_day", "is_instructional", "is_mandatory", "is_primary"]); return Object.fromEntries(config.fields.map((field) => { if (mode === "bulk") return [field.name, field.type === "multiselect" ? [] : field.type === "boolean" ? false : ""]; const fallback = field.type === "boolean" ? trueDefaults.has(field.name) : undefined; const value = initial?.[field.name] ?? field.defaultValue ?? fallback; return [field.name, Array.isArray(value) ? value.map(String) : field.type === "boolean" ? Boolean(value) : value == null ? "" : String(value)]; })); }

function validate(config: MasterConfig, values: Record<string, FormValue>, only?: Set<string>, lookupRecords: Record<string, MasterRecord[]> = {}) {
  const errors: Record<string, string> = {};
  for (const field of config.fields) { if (!isVisible(field, values) || only && !only.has(field.name)) continue; const value = values[field.name]; if (field.required && (value === "" || value == null || Array.isArray(value) && !value.length)) errors[field.name] = `${field.label} is required.`; if (field.type === "email" && value && !/^\S+@\S+\.\S+$/.test(String(value))) errors[field.name] = "Enter a valid email address."; if (field.type === "number" && value !== "") { const numberValue = Number(value); if (!Number.isFinite(numberValue)) errors[field.name] = "Enter a valid number."; else if (field.min != null && numberValue < field.min) errors[field.name] = `Must be at least ${field.min}.`; else if (field.max != null && numberValue > field.max) errors[field.name] = `Must be at most ${field.max}.`; } }
  const get = (name: string) => Number(values[name]);
  if (config.slug === "faculty" && get("maximum_weekly_workload") < get("minimum_weekly_workload")) errors.maximum_weekly_workload = "Maximum workload must be at least the minimum.";
  if (config.slug === "academic-terms") { if (String(values.start_date) >= String(values.end_date)) errors.end_date = "End date must be after start date."; const years = ["I", "II", "III", "IV"]; const expected = `${years[get("year_number") - 1]}-${get("semester_number") === 1 ? "I" : "II"}`; if (values.term_name && String(values.term_name) !== expected) errors.term_name = `Term must be ${expected} for the selected year and semester.`; }
  if (config.slug === "student-batches" && get("roll_number_start") > get("roll_number_end")) errors.roll_number_end = "Roll number end must not precede the start.";
  if (config.slug === "student-batches" && get("student_count") !== get("roll_number_end") - get("roll_number_start") + 1) errors.student_count = "Student count must match the roll-number range.";
  if (config.slug === "laboratory-allocations" && values.minimum_sessions_per_week && values.maximum_sessions_per_week && get("maximum_sessions_per_week") < get("minimum_sessions_per_week")) errors.maximum_sessions_per_week = "Maximum sessions must be at least the minimum.";
  if (config.slug === "classroom-assignments" && values.effective_from && values.effective_to && String(values.effective_from) > String(values.effective_to)) errors.effective_to = "Effective-to date must not precede effective-from date.";
  if (config.slug === "courses") { const eligible = Array.isArray(values.eligible_laboratory_ids) ? values.eligible_laboratory_ids : []; if (get("weekly_periods") !== get("session_duration") * get("sessions_per_week")) errors.weekly_periods = "Weekly periods must equal session duration × sessions per week."; if (values.venue_requirement === "LABORATORY_ONLY" && !eligible.length) errors.eligible_laboratory_ids = "A laboratory-only activity requires at least one eligible laboratory."; if (values.default_laboratory_id && !eligible.includes(String(values.default_laboratory_id))) errors.default_laboratory_id = "Preferred laboratory must be selected as eligible."; }
  if (config.slug === "course-offerings") { const course = (lookupRecords["/courses"] ?? []).find((row) => row.id === String(values.course_id ?? "")); const mode = String(values.laboratory_selection_mode || "AUTO"); if (isLaboratoryCapableCourse(course) && ["PREFERRED", "FIXED"].includes(mode) && !values.laboratory_override_id) errors.laboratory_override_id = `${mode === "FIXED" ? "Required" : "Preferred"} laboratory is required.`; }
  if (config.slug === "combined-teaching-groups" && (!Array.isArray(values.course_offering_ids) || values.course_offering_ids.length < 2)) errors.course_offering_ids = "Select at least two participating course offerings.";
  return errors;
}

function CombinedTeachingSummary({ values, lookupRecords }: { values: Record<string, FormValue>; lookupRecords: Record<string, MasterRecord[]> }) {
  const selected = new Set(Array.isArray(values.course_offering_ids) ? values.course_offering_ids : []);
  const offerings = (lookupRecords["/course-offerings"] ?? []).filter((row) => selected.has(row.id));
  const rows = offerings.map((offering) => ({ id: offering.id, label: String(offering.display_label ?? offering.section_code ?? "Section metadata unavailable"), strength: Number(offering.section_strength ?? 0) }));
  const combinedStrength = rows.reduce((total, row) => total + row.strength, 0);
  const room = (lookupRecords["/classrooms"] ?? []).find((row) => row.id === values.preferred_classroom_id);
  const capacity = room?.capacity == null ? undefined : Number(room.capacity);
  const status = capacity == null ? "Capacity not configured" : capacity >= combinedStrength ? "Capacity OK" : "Capacity exceeded";
  return <section className="sm:col-span-2 rounded-lg border bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900" aria-label="Combined teaching capacity summary"><h3 className="font-semibold">Combined class summary</h3>{rows.length ? <><ul className="mt-2 space-y-1 text-sm">{rows.map((row) => <li key={row.id}>{row.label}: {row.strength} students</li>)}</ul><div className="mt-3 flex flex-wrap gap-3 text-sm"><strong>Combined strength: {combinedStrength}</strong><span>Room capacity: {capacity ?? "Not configured"}</span><span className={capacity != null && capacity < combinedStrength ? "font-semibold text-red-700" : "font-semibold text-emerald-700"}>{status}</span></div></> : <p className="mt-2 text-sm text-slate-500">Select offerings to calculate section strength and capacity.</p>}</section>;
}

export function toPayload(config: MasterConfig, values: Record<string, FormValue>, only?: Set<string>, lookupRecords: Record<string, MasterRecord[]> = {}) { const payload: Record<string, unknown> = {}; for (const field of config.fields) { if (!isVisible(field, values) || only && !only.has(field.name)) continue; const value = values[field.name]; if (value === "" || value == null || Array.isArray(value) && !value.length) { if (!only && !field.required) payload[field.name] = field.type === "multiselect" ? [] : null; continue; } payload[field.name] = field.type === "number" ? Number(value) : value; } if (config.slug === "courses" && (!only || only.has("grouping_mode")) && values.grouping_mode === "FULL_SECTION") payload.default_group_count = 1; if (config.slug === "courses" && (!only || only.has("venue_requirement")) && !["LABORATORY_ONLY", "CLASSROOM_OR_LABORATORY"].includes(String(values.venue_requirement))) { payload.default_laboratory_id = null; payload.eligible_laboratory_ids = []; } if (config.slug === "course-offerings") { const course = (lookupRecords["/courses"] ?? []).find((row) => row.id === String(values.course_id ?? "")); if (course) normalizeOfferingLaboratoryPayload(payload, course); else if (values.laboratory_selection_mode === "AUTO") payload.laboratory_override_id = null; } return payload; }

function filteredLookups(config: MasterConfig, field: MasterField, values: Record<string, FormValue>, lookupRecords: Record<string, MasterRecord[]>) {
  if (field.lookup?.endpoint !== "/laboratories") return lookupRecords;
  let allowed: string[] | undefined;
  if (config.slug === "courses" && field.name === "default_laboratory_id") allowed = Array.isArray(values.eligible_laboratory_ids) ? values.eligible_laboratory_ids : [];
  if (config.slug === "course-offerings" && field.name === "laboratory_override_id") {
    const course = (lookupRecords["/courses"] ?? []).find((row) => row.id === values.course_id);
    allowed = Array.isArray(course?.eligible_laboratory_ids) ? course.eligible_laboratory_ids.map(String) : course?.default_laboratory_id ? [String(course.default_laboratory_id)] : [];
  }
  if (config.slug === "combined-teaching-groups" && field.name === "preferred_laboratory_id") {
    const course = (lookupRecords["/courses"] ?? []).find((row) => row.id === values.course_id);
    allowed = Array.isArray(course?.eligible_laboratory_ids) ? course.eligible_laboratory_ids.map(String) : course?.default_laboratory_id ? [String(course.default_laboratory_id)] : [];
  }
  return allowed ? { ...lookupRecords, "/laboratories": (lookupRecords["/laboratories"] ?? []).filter((row) => allowed!.includes(row.id)) } : lookupRecords;
}
export function coerceCsvRow(config: MasterConfig, row: Record<string, string>) { const values: Record<string, FormValue> = {}; for (const field of config.fields) { const raw = row[field.name] || (typeof field.defaultValue === "string" ? field.defaultValue : ""); values[field.name] = field.type === "boolean" ? ["true", "1", "yes", "y"].includes(raw.toLowerCase()) : field.type === "multiselect" ? raw.split(/[|;]/).map((item) => item.trim()).filter(Boolean) : raw; } return { payload: toPayload(config, values), errors: validate(config, values) }; }
