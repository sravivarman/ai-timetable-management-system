import axios from "axios";
import { api } from "@/lib/api-client";

export type ResourceAvailabilityMode="ALL_PERIODS"|"EXCEPT_BLOCKED"|"ONLY_SELECTED";
export type ResourceAvailabilityProfile={id:string;resource_type:string;resource_id:string;academic_term_id:string;availability_mode:ResourceAvailabilityMode;is_active:boolean;created_at?:string;updated_at?:string};
export type ResourceAvailabilitySlot={id:string;resource_type:string;resource_id:string;academic_term_id:string;working_day_id:string;period_number:number;availability_type:"BLOCKED"|"ALLOWED";reason?:string|null;is_active:boolean};
type Page<T>={items:T[]};

export async function getResourceAvailabilityProfile(resourceType:string,resourceId:string,academicTermId:string):Promise<ResourceAvailabilityProfile|null>{
 try{
  const response=await api.get<Page<ResourceAvailabilityProfile>>("/resource-availability/profiles",{params:{resource_type:resourceType,resource_id:resourceId,academic_term_id:academicTermId,page_size:1}});
  if(!Array.isArray(response.data.items))throw new Error("Resource availability profile response is invalid.");
  return response.data.items[0]??null;
 }catch(error){
  if(axios.isAxiosError(error)&&error.response?.status===404)return null;
  throw error;
 }
}

export async function getResourceAvailabilitySlots(resourceType:string,resourceId:string,academicTermId:string):Promise<ResourceAvailabilitySlot[]>{
 const response=await api.get<Page<ResourceAvailabilitySlot>>("/resource-availability/slots",{params:{resource_type:resourceType,resource_id:resourceId,academic_term_id:academicTermId,page_size:100}});
 if(!Array.isArray(response.data.items))throw new Error("Resource availability slot response is invalid.");
 return response.data.items;
}
