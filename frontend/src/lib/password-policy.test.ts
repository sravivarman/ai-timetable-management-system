import { describe, expect, it } from "vitest";
import { isValidNewPassword, MINIMUM_PASSWORD_LENGTH, PASSWORD_MINIMUM_MESSAGE } from "@/lib/password-policy";

describe("new password policy", () => {
  it("uses the shared eight-character minimum and message", () => {
    expect(MINIMUM_PASSWORD_LENGTH).toBe(8);
    expect(PASSWORD_MINIMUM_MESSAGE).toBe("Password must be at least 8 characters.");
    expect(isValidNewPassword("1234567")).toBe(false);
    expect(isValidNewPassword("12345678")).toBe(true);
    expect(isValidNewPassword("LongerPassword123")).toBe(true);
  });
});
