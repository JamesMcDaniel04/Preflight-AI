import { useEffect, useRef, useState } from "react";
import { getOpenAIKey, setOpenAIKey, maskKey } from "../keyStore";

export default function SettingsPanel({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState("");
  const [stored, setStored] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const k = getOpenAIKey();
    setStored(k);
    setDraft("");
    setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  if (!open) return null;

  function save() {
    const trimmed = draft.trim();
    if (!trimmed) return;
    setOpenAIKey(trimmed);
    setStored(trimmed);
    setDraft("");
    onClose();
  }

  function clear() {
    setOpenAIKey(null);
    setStored(null);
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="font-semibold">Settings</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-lg">
            &times;
          </button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              OpenAI API key
            </label>
            <p className="text-xs text-slate-500 mb-2">
              Stored locally in your browser. Sent only as a per-request header.
              Never persisted on our servers.
            </p>
            {stored ? (
              <div className="flex items-center justify-between rounded-md bg-slate-50 border border-slate-200 px-3 py-2 text-sm font-mono">
                <span>{maskKey(stored)}</span>
                <button
                  onClick={clear}
                  className="text-xs text-red-600 hover:underline font-sans"
                >
                  Remove
                </button>
              </div>
            ) : (
              <div className="text-xs text-slate-500 italic">No key set.</div>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {stored ? "Replace key" : "Set key"}
            </label>
            <input
              ref={inputRef}
              type="password"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") save();
              }}
              placeholder="sk-..."
              autoComplete="off"
              className="w-full rounded-md border border-slate-300 p-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400"
            />
          </div>
        </div>
        <div className="px-6 py-3 border-t border-slate-200 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm rounded-md border border-slate-300 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            onClick={save}
            disabled={!draft.trim()}
            className="px-4 py-1.5 text-sm rounded-md bg-sky-600 text-white hover:bg-sky-700 disabled:bg-slate-300"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
