import type { ImportLookupRecords } from "@/lib/csv-import-resolution";
import { compactAvailabilityPeriods, resolveLaboratoryAvailabilityCsv } from "@/lib/laboratory-availability-csv";
import type { MasterRecord } from "@/lib/master-data-api";

export const RESOURCE_AVAILABILITY_HEADERS=["resource_type","resource_code","academic_term_code","availability_mode","blocked_periods","allowed_periods"];
const resources:Record<string,{endpoint:string;code:string}>={
 FACULTY:{endpoint:"/faculty",code:"faculty_code"},VISITING_FACULTY:{endpoint:"/faculty",code:"faculty_code"},LABORATORY:{endpoint:"/laboratories",code:"laboratory_code"},CLASSROOM:{endpoint:"/classrooms",code:"room_number"},SEMINAR_HALL:{endpoint:"/classrooms",code:"room_number"},SMART_CLASSROOM:{endpoint:"/classrooms",code:"room_number"},DRAWING_HALL:{endpoint:"/classrooms",code:"room_number"},WORKSHOP_ROOM:{endpoint:"/classrooms",code:"room_number"},WORKSHOP:{endpoint:"/classrooms",code:"room_number"},GUEST_LECTURE_HALL:{endpoint:"/classrooms",code:"room_number"},GUEST_HALL:{endpoint:"/classrooms",code:"room_number"},
};
export type ResolvedResourceAvailability={profile?:{resource_type:string;resource_id:string;academic_term_id:string;availability_mode:string};slots:{resource_type:string;resource_id:string;academic_term_id:string;working_day_id:string;period_number:number;availability_type:"BLOCKED"|"ALLOWED"}[];resolvedResource?:MasterRecord;errors:string[]};

export function resolveResourceAvailabilityCsv(row:Record<string,string>,lookups:ImportLookupRecords):ResolvedResourceAvailability{
 const type=String(row.resource_type??"").trim().toUpperCase();const definition=resources[type];const errors:string[]=[];
 if(!definition)return {slots:[],errors:[`Unknown resource_type '${row.resource_type}'.`]};
 const code=String(row.resource_code??"").trim().toUpperCase();const all=lookups[definition.endpoint]??[];const matches=all.filter((item)=>String(item[definition.code]??"").trim().toUpperCase()===code);
 const active=matches.filter((item)=>item.is_active!==false);if(!active.length)errors.push(matches.length?`Resource '${row.resource_code}' is inactive.`:`Unknown resource code '${row.resource_code}'.`);if(active.length>1)errors.push(`Ambiguous resource code '${row.resource_code}'.`);
 const availability=resolveLaboratoryAvailabilityCsv(row,lookups);errors.push(...availability.errors);const resource=active.length===1?active[0]:undefined;
 const termCode=String(row.academic_term_code??"").trim().toUpperCase().replace(/\s*(?:\||\/|:)\s*/,"|").replace(/\s+/,"|");const terms=(lookups["/academic-terms"]??[]).filter((term)=>term.is_active!==false&&`${term.academic_year}|${term.term_name}`.toUpperCase()===termCode);const term=terms.length===1?terms[0]:undefined;
 if(!term)errors.push(terms.length>1?`Ambiguous academic term '${row.academic_term_code}'.`:`Unknown or inactive academic term '${row.academic_term_code}'.`);
 if(!resource||!term)return {resolvedResource:resource,slots:[],errors:[...new Set(errors)]};
 return {resolvedResource:resource,profile:{resource_type:type,resource_id:resource.id,academic_term_id:term.id,availability_mode:String(row.availability_mode||"ALL_PERIODS").toUpperCase()},slots:availability.slots.map((slot)=>({...slot,resource_type:type,resource_id:resource.id})),errors:[...new Set(errors)]};
}

export function resourceAvailabilityTemplate(resourceType="LABORATORY"){return [{resource_type:resourceType,resource_code:"",academic_term_code:"2026-27|I-I",availability_mode:"ALL_PERIODS",blocked_periods:"",allowed_periods:""}]}

export function resourceAvailabilityExportRows(
 resourceType:string,resource:MasterRecord,term:MasterRecord,mode:string,slots:MasterRecord[],days:MasterRecord[],
):Record<string,unknown>[] {
 const type=resourceType.trim().toUpperCase();const definition=resources[type];
 if(!definition)throw new Error(`No readable export key is configured for resource type '${resourceType}'.`);
 const code=resource[definition.code];
 if(code==null||code==="")throw new Error(`The selected ${type.replaceAll("_"," ").toLowerCase()} has no readable business key.`);
 if(!term.academic_year||!term.term_name)throw new Error("The selected academic term has no readable business key.");
 return [{resource_type:type,resource_code:String(code),academic_term_code:`${term.academic_year} | ${term.term_name}`,availability_mode:mode,blocked_periods:compactAvailabilityPeriods(slots,days,"BLOCKED"),allowed_periods:compactAvailabilityPeriods(slots,days,"ALLOWED")}];
}
