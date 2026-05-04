import { RefObject, useEffect, useRef, useState } from "react";
import {
  getAnthropicKey,
  getOpenAIKey,
  maskKey,
  setProviderKey,
} from "../keyStore";

export default function SettingsPanel({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [openaiDraft, setOpenaiDraft] = useState("");
  const [anthropicDraft, setAnthropicDraft] = useState("");
  const [openaiStored, setOpenaiStored] = useState<string | null>(null);
  const [anthropicStored, setAnthropicStored] = useState<string | null>(null);
  const openaiInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setOpenaiStored(getOpenAIKey());
    setAnthropicStored(getAnthropicKey());
    setOpenaiDraft("");
    setAnthropicDraft("");
    setTimeout(() => openaiInputRef.current?.focus(), 50);
  }, [open]);

  if (!open) return null;

  function save() {
    const nextOpenai = openaiDraft.trim() || openaiStored;
    const nextAnthropic = anthropicDraft.trim() || anthropicStored;
    setProviderKey("openai", nextOpenai ?? null);
    setProviderKey("anthropic", nextAnthropic ?? null);
    setOpenaiStored(nextOpenai ?? null);
    setAnthropicStored(nextAnthropic ?? null);
    setOpenaiDraft("");
    setAnthropicDraft("");
    onClose();
  }

  function clear(provider: "openai" | "anthropic") {
    setProviderKey(provider, null);
    if (provider === "openai") setOpenaiStored(null);
    else setAnthropicStored(null);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="mx-4 w-full max-w-lg rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h2 className="font-semibold">Settings</h2>
          <button onClick={onClose} className="text-lg text-slate-400 hover:text-slate-600">
            &times;
          </button>
        </div>
        <div className="space-y-5 px-6 py-5">
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
            Provider keys stay in this browser only. Async runs pass them through the backend and
            into the Celery task payload transiently so the worker can finish the run. They are not
            stored in the app database.
          </div>
          <KeySection
            title="OpenAI API key"
            stored={openaiStored}
            draft={openaiDraft}
            onDraftChange={setOpenaiDraft}
            onClear={() => clear("openai")}
            inputRef={openaiInputRef}
            placeholder="sk-..."
          />
          <KeySection
            title="Anthropic API key"
            stored={anthropicStored}
            draft={anthropicDraft}
            onDraftChange={setAnthropicDraft}
            onClear={() => clear("anthropic")}
            placeholder="sk-ant-..."
          />
          <div className="text-xs text-slate-500">
            Anthropic simulation runs still require an OpenAI key for embeddings, clustering, and
            dangerous-failure analysis.
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-200 px-6 py-3">
          <button
            onClick={onClose}
            className="rounded-md border border-slate-300 px-4 py-1.5 text-sm hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            onClick={save}
            className="rounded-md bg-sky-600 px-4 py-1.5 text-sm text-white hover:bg-sky-700"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

function KeySection({
  title,
  stored,
  draft,
  onDraftChange,
  onClear,
  placeholder,
  inputRef,
}: {
  title: string;
  stored: string | null;
  draft: string;
  onDraftChange: (value: string) => void;
  onClear: () => void;
  placeholder: string;
  inputRef?: RefObject<HTMLInputElement>;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">{title}</label>
      {stored ? (
        <div className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-mono">
          <span>{maskKey(stored)}</span>
          <button onClick={onClear} className="text-xs text-red-600 hover:underline font-sans">
            Remove
          </button>
        </div>
      ) : (
        <div className="text-xs italic text-slate-500">No key set.</div>
      )}
      <input
        ref={inputRef}
        type="password"
        value={draft}
        onChange={(event) => onDraftChange(event.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        className="mt-2 w-full rounded-md border border-slate-300 p-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400"
      />
    </div>
  );
}
