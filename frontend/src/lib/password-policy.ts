export const MINIMUM_PASSWORD_LENGTH = 8;
export const PASSWORD_MINIMUM_MESSAGE = "Password must be at least 8 characters.";

export function isValidNewPassword(password: string): boolean {
  return password.length >= MINIMUM_PASSWORD_LENGTH;
}
