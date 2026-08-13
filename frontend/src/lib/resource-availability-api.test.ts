import { beforeEach,describe,expect,it,vi } from "vitest";
import { api } from "@/lib/api-client";
import { getResourceAvailabilityProfile } from "@/lib/resource-availability-api";

vi.mock("@/lib/api-client",()=>({api:{get:vi.fn()}}));
const page=(items:unknown[])=>({data:{items}});
const failure=(status?:number)=>Object.assign(new Error(status?`HTTP ${status}`:"Network failure"),{isAxiosError:true,response:status?{status}:undefined});

describe("resource availability API",()=>{
 beforeEach(()=>vi.clearAllMocks());
 it.each(["CLASSROOM","LABORATORY","FACULTY"])("returns null when %s has no profile",async(resourceType)=>{vi.mocked(api.get).mockResolvedValue(page([]));await expect(getResourceAvailabilityProfile(resourceType,"resource-1","term-1")).resolves.toBeNull()});
 it("treats a 404 as an expected missing profile",async()=>{vi.mocked(api.get).mockRejectedValue(failure(404));await expect(getResourceAvailabilityProfile("CLASSROOM","resource-1","term-1")).resolves.toBeNull()});
 it.each([[403,"403"],[500,"500"],[undefined,"Network failure"]])("does not swallow unexpected failure %s",async(status,message)=>{vi.mocked(api.get).mockRejectedValue(failure(status as number|undefined));await expect(getResourceAvailabilityProfile("FACULTY","resource-1","term-1")).rejects.toThrow(String(message))});
});
