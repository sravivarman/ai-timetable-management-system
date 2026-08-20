import {describe,expect,it} from "vitest";
import {resolveSemesterRequirementRows,semesterRequirementTemplate} from "@/lib/semester-requirement-csv";
import type {SlotRequirementMatrix} from "@/lib/types";

const matrix={slots:[],completeness:[],rows:[{course_offering_id:"offering-1",section_id:"section-1",course_code:"A9001",course_name:"Theory",course_type:"THEORY",section_code:"CSE-A",section_name:"A",semester_requirement_id:"semester-1",semester_required:42,allocated_to_slots:38,remaining_to_allocate:4,over_allocated:0,reconciliation_status:"UNDER_ALLOCATED",cells:[]}]} satisfies SlotRequirementMatrix;
describe("semester requirement CSV",()=>{
 it("uses business keys and detects changed values",()=>{const [row]=resolveSemesterRequirementRows([{academic_term_code:"2026-27 I-I",course_code:"A9001",section_code:"CSE-A",total_sessions_required:"44",is_active:"true"}],matrix,"2026-27 I-I");expect(row.status).toBe("CHANGED");expect(row.course_offering_id).toBe("offering-1")});
 it("contains no UUID columns",()=>expect(Object.keys(semesterRequirementTemplate()[0]).some((key)=>key.endsWith("_id"))).toBe(false));
 it("rejects contradictory duplicate business keys",()=>{const rows=resolveSemesterRequirementRows([{academic_term_code:"2026-27 I-I",course_code:"A9001",section_code:"CSE-A",total_sessions_required:"42",is_active:"true"},{academic_term_code:"2026-27 I-I",course_code:"A9001",section_code:"CSE-A",total_sessions_required:"43",is_active:"true"}],matrix,"2026-27 I-I");expect(rows.every((row)=>row.status==="CONFLICT")).toBe(true)});
});
