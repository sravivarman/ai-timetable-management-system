import type { SlotRequirementMatrix } from "@/lib/types";

export const SEMESTER_REQUIREMENT_CSV_HEADERS=["academic_term_code","course_code","section_code","total_sessions_required","is_active"] as const;
export type SemesterCsvStatus="NEW"|"IDENTICAL"|"CHANGED"|"INVALID"|"CONFLICT";
export type ResolvedSemesterRequirement={rowNumber:number;source:Record<string,string>;status:SemesterCsvStatus;message?:string;course_offering_id?:string;total_sessions_required?:number;existing?:number|null};

export function semesterRequirementTemplate(){return[{academic_term_code:"2026-27 I-I",course_code:"A9001",section_code:"CSE-A",total_sessions_required:"42",is_active:"true"}]}

export function resolveSemesterRequirementRows(rows:Record<string,string>[],matrix:SlotRequirementMatrix,termLabel:string):ResolvedSemesterRequirement[]{
 const seen=new Map<string,ResolvedSemesterRequirement>();
 return rows.map((source,index)=>{
  const base:ResolvedSemesterRequirement={rowNumber:index+2,source,status:"INVALID"};
  if(normalize(source.academic_term_code)!==normalize(termLabel))return{...base,message:`Unknown Academic Term '${source.academic_term_code}'.`};
  const matches=matrix.rows.filter((row)=>normalize(row.course_code)===normalize(source.course_code)&&normalize(row.section_code)===normalize(source.section_code));
  if(matches.length!==1)return{...base,status:matches.length?"CONFLICT":"INVALID",message:matches.length?"Course/Section resolves to multiple Course Offerings.":"Course Offering was not found for this course and section."};
  if(!/^\d+$/.test(String(source.total_sessions_required??"").trim()))return{...base,message:"total_sessions_required must be a non-negative whole number."};
  if(source.is_active&&!["TRUE","YES","1"].includes(normalize(source.is_active)))return{...base,message:"is_active must be true for an imported requirement; use the UI to deactivate records."};
  const match=matches[0],total=Number(source.total_sessions_required),existing=match.semester_required??null;
  const resolved:ResolvedSemesterRequirement={...base,status:existing==null?"NEW":existing===total?"IDENTICAL":"CHANGED",course_offering_id:match.course_offering_id,total_sessions_required:total,existing};
  const duplicate=seen.get(match.course_offering_id);if(duplicate){if(duplicate.total_sessions_required!==total){duplicate.status="CONFLICT";duplicate.message="Contradictory duplicate business key in CSV.";resolved.status="CONFLICT";resolved.message=duplicate.message}else{resolved.status="IDENTICAL";resolved.message=`Duplicate of row ${duplicate.rowNumber}.`}}else seen.set(match.course_offering_id,resolved);
  return resolved;
 });
}
function normalize(value:string|undefined){return String(value??"").trim().replace(/\s+/g," ").toUpperCase()}
