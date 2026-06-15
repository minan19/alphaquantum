/**
 * M3: AI Copilot API client.
 *
 * İki adımlı akış:
 *  - askCopilot(query, confirm=false) → preview: intent + tam SQL + paramlar
 *  - askCopilot(query, confirm=true)  → onay sonrası çalıştırma: results dolar
 *
 * Tenant scope sunucuda enjekte edilir; client şirket parametresi göndermez.
 * Bu modül guardrail değildir — backend zorlar.
 */
import { apiRequest } from "@/lib/api";

export interface CopilotIntent {
  intent: string;
  entity_name: string | null;
  time_window_days: number | null;
  direction: string | null;
  category: string | null;
  confidence_pct: number;
  raw_query: string;
}

export interface CopilotResponse {
  intent: CopilotIntent;
  results: Array<Record<string, unknown>>;
  summary_text: string;
  explanation: string;
  sql_template_used: string | null;
  sql: string | null;
  params: Array<string | number | boolean | null>;
  executed: boolean;
}

export function askCopilot(
  query: string,
  confirm: boolean,
): Promise<CopilotResponse> {
  return apiRequest<CopilotResponse>("/api/v1/copilot/ask", {
    method: "POST",
    body: { query, confirm },
  });
}
