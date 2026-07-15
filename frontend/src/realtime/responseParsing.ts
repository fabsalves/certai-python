export function parseFunctionCallArgs(call: { arguments?: unknown }): Record<string, unknown> {
  try {
    const raw = call.arguments;
    return typeof raw === "string" ? JSON.parse(raw || "{}") : (raw as Record<string, unknown>) || {};
  } catch {
    return {};
  }
}

function pushNormalizedFunctionCall(
  out: Array<{ name: string; call_id: string; arguments: string }>,
  raw: Record<string, unknown>,
) {
  const name = (raw.name || (raw.function as { name?: string } | undefined)?.name) as string | undefined;
  if (!name) return;
  const call_id = String(raw.call_id || raw.id || "");
  const args = raw.arguments ?? (raw.function as { arguments?: unknown } | undefined)?.arguments ?? "{}";
  out.push({
    name,
    call_id,
    arguments: typeof args === "string" ? args : JSON.stringify(args),
  });
}

export function collectFunctionCallsFromOutput(output: unknown[]): Array<{
  name: string;
  call_id: string;
  arguments: string;
}> {
  const out: Array<{ name: string; call_id: string; arguments: string }> = [];
  for (const item of output) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;

    if (row.type === "function" && row.function) {
      pushNormalizedFunctionCall(out, row);
      continue;
    }
    if (row.type === "function_call") {
      pushNormalizedFunctionCall(out, row);
      continue;
    }
    if (row.type === "message" && Array.isArray(row.content)) {
      for (const part of row.content) {
        if (part && typeof part === "object" && (part as { type?: string }).type === "function_call") {
          pushNormalizedFunctionCall(out, part as Record<string, unknown>);
        }
      }
    }
    if (row.type === "message" && Array.isArray(row.tool_calls)) {
      for (const tc of row.tool_calls) {
        pushNormalizedFunctionCall(out, tc as Record<string, unknown>);
      }
    }
  }
  return out;
}

export function normalizeRealtimeResponseOutput(response: { output?: unknown } | undefined): unknown[] {
  const raw = response?.output;
  if (Array.isArray(raw)) return raw;
  if (raw && typeof raw === "object" && Array.isArray((raw as { items?: unknown[] }).items)) {
    return (raw as { items: unknown[] }).items;
  }
  return [];
}

export function extractAssistantText(output: unknown[]): string {
  const parts: string[] = [];
  for (const item of output) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;

    if (row.type === "output_text" && typeof row.text === "string") {
      parts.push(row.text);
    }

    if (Array.isArray(row.content)) {
      for (const part of row.content) {
        if (!part || typeof part !== "object") continue;
        const p = part as Record<string, unknown>;
        const partType = p.type;

        if ((partType === "output_text" || partType === "text") && typeof p.text === "string") {
          parts.push(p.text);
        } else if (
          (partType === "output_audio" || partType === "audio" || partType === "audio_output") &&
          typeof p.transcript === "string"
        ) {
          parts.push(p.transcript);
        } else if (typeof p.transcript === "string" && p.transcript.trim()) {
          parts.push(p.transcript);
        }
      }
    }

    if (typeof row.transcript === "string" && row.transcript.trim()) {
      parts.push(row.transcript);
    }
  }
  return parts.join(" ").trim();
}

export function responseId(response: unknown): string {
  if (!response || typeof response !== "object") return `turn-${Date.now()}`;
  const id = (response as { id?: unknown }).id;
  return typeof id === "string" && id ? id : `turn-${Date.now()}`;
}

const AUDIO_OUTPUT_PART_TYPES = new Set(["output_audio", "audio", "audio_output"]);

export function responseHasAudioOutput(output: unknown[]): boolean {
  for (const item of output) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    if (row.type === "output_audio" || row.type === "audio" || row.type === "audio_output") {
      return true;
    }
    if (!Array.isArray(row.content)) continue;
    for (const part of row.content) {
      if (!part || typeof part !== "object") continue;
      const partType = (part as { type?: string }).type;
      if (partType && AUDIO_OUTPUT_PART_TYPES.has(partType)) {
        return true;
      }
    }
  }
  return false;
}
