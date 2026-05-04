const STORAGE_KEYS = {
  openai: "preflight.openai_key",
  anthropic: "preflight.anthropic_key",
} as const;

export type ProviderKeyName = keyof typeof STORAGE_KEYS;

function getStorageKey(provider: ProviderKeyName): string {
  return STORAGE_KEYS[provider];
}

export function getProviderKey(provider: ProviderKeyName): string | null {
  try {
    return localStorage.getItem(getStorageKey(provider));
  } catch {
    return null;
  }
}

export function setProviderKey(provider: ProviderKeyName, key: string | null): void {
  try {
    const storageKey = getStorageKey(provider);
    if (key) localStorage.setItem(storageKey, key);
    else localStorage.removeItem(storageKey);
  } catch {
    /* localStorage disabled */
  }
}

export function getOpenAIKey(): string | null {
  return getProviderKey("openai");
}

export function getAnthropicKey(): string | null {
  return getProviderKey("anthropic");
}

export function maskKey(key: string): string {
  if (key.length <= 8) return "*".repeat(key.length);
  return `${key.slice(0, 3)}...${key.slice(-4)}`;
}
