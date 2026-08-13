import { describe,expect,it,vi } from "vitest";
import { tokenStore } from "@/lib/token-store";

describe("tokenStore",()=>{
 it("stores, exposes, and clears a token pair without logging values",()=>{const logger=vi.spyOn(console,"log");tokenStore.set({access_token:"access-secret",refresh_token:"refresh-secret",token_type:"bearer"});expect(tokenStore.access()).toBe("access-secret");expect(tokenStore.refresh()).toBe("refresh-secret");expect(tokenStore.hasSession()).toBe(true);expect(logger).not.toHaveBeenCalled();tokenStore.clear();expect(tokenStore.access()).toBeNull();expect(tokenStore.hasSession()).toBe(false);logger.mockRestore()});
 it("notifies session listeners",()=>{const listener=vi.fn();const unsubscribe=tokenStore.subscribe(listener);tokenStore.set({access_token:"a",refresh_token:"r",token_type:"bearer"});expect(listener).toHaveBeenCalledOnce();unsubscribe()});
});
