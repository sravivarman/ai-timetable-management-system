import { describe,expect,it } from "vitest";
import { RESOURCE_AVAILABILITY_HEADERS,resolveResourceAvailabilityCsv } from "@/lib/resource-availability-csv";

const lookups={
 "/classrooms":[{id:"room-uuid",room_number:"3204",room_name:"CSE Block",is_active:true}],
 "/laboratories":[{id:"lab-uuid",laboratory_code:"LAB3201",laboratory_name:"Programming Lab",is_active:true}],
 "/faculty":[{id:"faculty-uuid",faculty_code:"VCE042",full_name:"Dr Kumar",is_active:true}],
 "/academic-terms":[{id:"term-uuid",academic_year:"2026-27",term_name:"I-I",is_active:true}],
 "/working-days":[{id:"day-uuid",day_name:"Monday",sequence_number:1,is_active:true,is_working_day:true}],
};
describe("generic resource availability CSV",()=>{
 it("uses business keys and resolves them to internal UUID payloads",()=>{const result=resolveResourceAvailabilityCsv({resource_type:"CLASSROOM",resource_code:"3204",academic_term_code:"2026-27|I-I",availability_mode:"EXCEPT_BLOCKED",blocked_periods:"Mon:P2",allowed_periods:""},lookups);expect(result.errors).toEqual([]);expect(result.profile).toEqual({resource_type:"CLASSROOM",resource_id:"room-uuid",academic_term_id:"term-uuid",availability_mode:"EXCEPT_BLOCKED"});expect(result.slots[0]).toMatchObject({resource_id:"room-uuid",working_day_id:"day-uuid",period_number:2,availability_type:"BLOCKED"});expect(RESOURCE_AVAILABILITY_HEADERS.every((header)=>!header.endsWith("_id"))).toBe(true)});
 it("reports unknown and ambiguous readable resource codes",()=>{expect(resolveResourceAvailabilityCsv({resource_type:"FACULTY",resource_code:"NOPE",academic_term_code:"2026-27|I-I",availability_mode:"ALL_PERIODS",blocked_periods:"",allowed_periods:""},lookups).errors.join(" ")).toContain("Unknown resource code");const duplicate={...lookups,"/laboratories":[...lookups["/laboratories"],{...lookups["/laboratories"][0],id:"lab-two"}]};expect(resolveResourceAvailabilityCsv({resource_type:"LABORATORY",resource_code:"LAB3201",academic_term_code:"2026-27|I-I",availability_mode:"ALL_PERIODS",blocked_periods:"",allowed_periods:""},duplicate).errors.join(" ")).toContain("Ambiguous resource code")});
});
