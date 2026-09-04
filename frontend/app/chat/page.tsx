"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiClientError } from "@/lib/api";
import { useRun } from "@/lib/run-context";
import { PageHeader } from "@/components/ui";
import { motion } from "framer-motion";
import { SPRING } from "@/components/motion";

interface Msg {
  role: "user" | "assistant";
  text: string;
  intent?: string;
  grounded?: string[];
}

const SUGGESTIONS = [
  "Why is revenue down this week?",
  "What are the top loss causes?",
  "What did you do for cus_0117?",
];

export default function ChatPage() {
  const { version } = useRun();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => setMsgs([]), [version]);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [msgs]);

  async function ask(q: string) {
    const question = q.trim();
    if (!question || busy) return;
    setInput("");
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setBusy(true);
    try {
      const r = await api.chat(question);
      setMsgs((m) => [...m, { role: "assistant", text: r.answer, intent: r.intent, grounded: r.grounded_on }]);
    } catch (e) {
      setMsgs((m) => [
        ...m,
        {
          role: "assistant",
          text: e instanceof ApiClientError ? `${e.code}: ${e.message}` : "Cannot reach the API on :8000.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <PageHeader title="Chat" subtitle="Grounded in the current batch — aggregates, leak graph, audit log." />

      <div className="flex-1 space-y-3 overflow-y-auto pr-1">
        {msgs.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => ask(s)}
                className="rounded-full border border-surface-sunk bg-surface px-3 py-1.5 text-xs text-ink-soft shadow-float-sm hover:text-ink"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {msgs.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={SPRING}
            className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
          >
            <div
              className={`max-w-[80%] rounded-card px-4 py-2.5 text-sm leading-relaxed shadow-float-sm ${
                m.role === "user" ? "bg-sage-deep text-white" : "bg-surface text-ink"
              }`}
            >
              {m.text}
              {m.role === "assistant" && (m.intent || m.grounded?.length) && (
                <p className="mt-1.5 border-t border-surface-sunk pt-1.5 text-[10px] text-ink-soft">
                  {m.intent && <span className="mr-2 rounded bg-surface-sunk px-1">{m.intent}</span>}
                  {m.grounded?.join(" · ")}
                </p>
              )}
            </div>
          </motion.div>
        ))}
        {busy && <p className="text-xs text-ink-soft">thinking…</p>}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
        className="mt-3 flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about this batch…"
          className="flex-1 rounded-full border border-surface-sunk bg-surface px-4 py-2 text-sm text-ink outline-none focus:ring-1 focus:ring-sage"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-full bg-sage-deep px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
