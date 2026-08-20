import type { SlotRequirementMatrix } from "@/lib/types";

export const SLOT_REQUIREMENT_CSV_HEADERS=["academic_term","slot_code","course_code","section_code","sessions_required"] as const;
export type SlotCsvStatus="NEW"|"IDENTICAL"|"CHANGED"|"INVALID"|"CONFLICT";
export type ResolvedSlotRequirement={rowNumber:number;source:Record<string,string>;status:SlotCsvStatus;message?:string;scheduling_slot_id?:string;course_offering_id?:string;sessions_required?:number;existing?:number|null};

export function slotRequirementTemplate(){return [{academic_term:"2026-27 I-I",slot_code:"S01",course_code:"A9001",section_code:"CSE-A",sessions_required:"4"}]}

export function resolveSlotRequirementRows(rows:Record<string,string>[],matrix:SlotRequirementMatrix,academicTermLabel:string):ResolvedSlotRequirement[]{
 const seen=new Map<string,ResolvedSlotRequirement>();
 return rows.map((source,index)=>{
  const base:ResolvedSlotRequirement={rowNumber:index+2,source,status:"INVALID"};
  if(normalize(source.academic_term)!==normalize(academicTermLabel))return{...base,message:`Unknown Academic Term '${source.academic_term}'.`};
  const slots=matrix.slots.filter((slot)=>normalize(slot.slot_code)===normalize(source.slot_code));
  if(slots.length!==1)return{...base,status:slots.length?"CONFLICT":"INVALID",message:slots.length?`Slot code '${source.slot_code}' is ambiguous.`:`Unknown Slot code '${source.slot_code}'.`};
  const offerings=matrix.rows.filter((row)=>normalize(row.course_code)===normalize(source.course_code)&&normalize(row.section_code)===normalize(source.section_code));
  if(offerings.length!==1)return{...base,status:offerings.length?"CONFLICT":"INVALID",message:offerings.length?"Course/Section resolves to multiple Course Offerings.":"Course Offering was not found for this course and section."};
  if(!/^\d+$/.test(String(source.sessions_required??"").trim()))return{...base,message:"sessions_required must be a non-negative whole number."};
  const sessions=Number(source.sessions_required);const slot=slots[0];const offering=offerings[0];const cell=offering.cells.find((item)=>item.scheduling_slot_id===slot.id);const key=`${slot.id}:${offering.course_offering_id}`;
  const resolved:ResolvedSlotRequirement={...base,status:cell?.sessions_required==null?"NEW":cell.sessions_required===sessions?"IDENTICAL":"CHANGED",scheduling_slot_id:slot.id,course_offering_id:offering.course_offering_id,sessions_required:sessions,existing:cell?.sessions_required??null};
  const duplicate=seen.get(key);if(duplicate){if(duplicate.sessions_required!==sessions){duplicate.status="CONFLICT";duplicate.message="Contradictory duplicate business key in CSV.";resolved.status="CONFLICT";resolved.message=duplicate.message}else{resolved.status="IDENTICAL";resolved.message=`Duplicate of row ${duplicate.rowNumber}.`}}else seen.set(key,resolved);
  return resolved;
 });
}

function normalize(value:string|undefined){return String(value??"").trim().replace(/\s+/g," ").toUpperCase()}
