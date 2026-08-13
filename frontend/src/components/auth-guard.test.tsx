import { render,screen,waitFor } from "@testing-library/react";
import { beforeEach,describe,expect,it,vi } from "vitest";
import { AuthGuard } from "@/components/auth-guard";

const replace=vi.fn();let authState:{user:object|null;loading:boolean};
vi.mock("next/navigation",()=>({useRouter:()=>({replace}),usePathname:()=>"/timetables"}));
vi.mock("@/providers/auth-provider",()=>({useAuth:()=>authState}));
describe("AuthGuard",()=>{beforeEach(()=>{replace.mockReset()});it("redirects an unauthenticated visitor to login",async()=>{authState={user:null,loading:false};render(<AuthGuard><p>Protected</p></AuthGuard>);await waitFor(()=>expect(replace).toHaveBeenCalledWith("/login?next=%2Ftimetables"));expect(screen.queryByText("Protected")).not.toBeInTheDocument()});it("renders protected content for a session",()=>{authState={user:{id:"u"},loading:false};render(<AuthGuard><p>Protected</p></AuthGuard>);expect(screen.getByText("Protected")).toBeInTheDocument()})});
