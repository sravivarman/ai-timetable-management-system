import { render,screen,waitFor } from "@testing-library/react";
import { beforeEach,describe,expect,it,vi } from "vitest";
import { AuthGuard } from "@/components/auth-guard";

const replace=vi.fn();let authState:{user:{id:string;roles:{name:string}[]}|null;loading:boolean};
vi.mock("next/navigation",()=>({useRouter:()=>({replace}),usePathname:()=>"/timetables"}));
vi.mock("@/providers/auth-provider",()=>({useAuth:()=>authState}));
describe("AuthGuard",()=>{beforeEach(()=>{replace.mockReset()});it("redirects an unauthenticated visitor to login",async()=>{authState={user:null,loading:false};render(<AuthGuard><p>Protected</p></AuthGuard>);await waitFor(()=>expect(replace).toHaveBeenCalledWith("/login?next=%2Ftimetables"));expect(screen.queryByText("Protected")).not.toBeInTheDocument()});it("renders protected content for a session",()=>{authState={user:{id:"u",roles:[]},loading:false};render(<AuthGuard><p>Protected</p></AuthGuard>);expect(screen.getByText("Protected")).toBeInTheDocument()});it("redirects Report Viewer away from non-report screens",async()=>{authState={user:{id:"viewer",roles:[{name:"REPORT_VIEWER"}]},loading:false};render(<AuthGuard><p>Protected</p></AuthGuard>);await waitFor(()=>expect(replace).toHaveBeenCalledWith("/reports?report=administrative-faculty_master"));expect(screen.queryByText("Protected")).not.toBeInTheDocument()})});
