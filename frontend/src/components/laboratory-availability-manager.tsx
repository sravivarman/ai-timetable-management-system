"use client";
import { ResourceAvailabilityManager } from "@/components/resource-availability-manager";

/** Backward-compatible component name; all behavior uses the shared engine. */
export function LaboratoryAvailabilityManager({canManage=false,initialLaboratoryId="",initialTermId="",printable=false,occupiedPeriodCount}:{canManage?:boolean;initialLaboratoryId?:string;initialTermId?:string;printable?:boolean;occupiedPeriodCount?:number}){
 return <ResourceAvailabilityManager resourceType="LABORATORY" canManage={canManage} initialResourceId={initialLaboratoryId} initialTermId={initialTermId} printable={printable} occupiedPeriodCount={occupiedPeriodCount}/>;
}
