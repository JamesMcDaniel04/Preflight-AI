/**
 * Per-browser memory of the last HTTP endpoint config the user picked.
 *
 * URL and format are persisted in localStorage so the Submit form can prefill
 * them on next visit. Auth header is *not* stored — token-bearing strings stay
 * in memory only and clear on tab close. If we ever add an explicit "remember
 * this token" toggle we can opt-in there.
 */
import { EndpointFormat } from "./api";

const KEY_URL = "preflight.endpoint_url";
const KEY_FORMAT = "preflight.endpoint_format";

export type EndpointConfig = {
  url: string;
  format: EndpointFormat;
};

export function loadEndpointConfig(): EndpointConfig | null {
  try {
    const url = localStorage.getItem(KEY_URL);
    const fmt = localStorage.getItem(KEY_FORMAT) as EndpointFormat | null;
    if (!url || (fmt !== "simple" && fmt !== "openai_compat")) return null;
    return { url, format: fmt };
  } catch {
    return null;
  }
}

export function saveEndpointConfig(config: EndpointConfig | null): void {
  try {
    if (!config) {
      localStorage.removeItem(KEY_URL);
      localStorage.removeItem(KEY_FORMAT);
      return;
    }
    localStorage.setItem(KEY_URL, config.url);
    localStorage.setItem(KEY_FORMAT, config.format);
  } catch {
    /* localStorage disabled */
  }
}
