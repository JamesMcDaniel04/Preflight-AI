/**
 * BYOK key storage. The key lives in localStorage on the user's device and is
 * sent only as a per-request header to our backend, which forwards it to OpenAI
 * without persisting it.
 */
const STORAGE_KEY = "preflight.openai_key";

export function getOpenAIKey(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setOpenAIKey(key: string | null): void {
  try {
    if (key) localStorage.setItem(STORAGE_KEY, key);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* localStorage disabled — silently no-op */
  }
}

export function maskKey(key: string): string {
  if (key.length <= 8) return "•".repeat(key.length);
  return `${key.slice(0, 3)}…${key.slice(-4)}`;
}
