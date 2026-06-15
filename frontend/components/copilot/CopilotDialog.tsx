"use client";

/**
 * M3: AI Copilot dialog — Cmd+K içinden "AI'ya danış" seçilince açılır.
 *
 * Akış: soru yaz → "Sor" (preview) → SQL + params + intent görünür →
 * "Onaylayıp Çalıştır" → DataTable sonuçları.
 *
 * Guardrail backend'de zorlanır; bu komponent yalnız UX katmanı.
 * Tüm renkler semantic token (bg-card, text-foreground, ...). Hex YOK.
 */
import { useCallback, useEffect, useState } from "react";
import { Sparkles, ShieldCheck, Loader2, AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { askCopilot, type CopilotResponse } from "@/lib/copilot-api";
import { ApiError } from "@/lib/api";

type Stage = "compose" | "preview" | "executing" | "result" | "error";

interface CopilotDialogProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}

export function CopilotDialog({ open, onOpenChange }: CopilotDialogProps) {
  const [stage, setStage] = useState<Stage>("compose");
  const [query, setQuery] = useState("");
  const [preview, setPreview] = useState<CopilotResponse | null>(null);
  const [result, setResult] = useState<CopilotResponse | null>(null);
  const [error, setError] = useState<{ title: string; detail: string } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);

  // Dialog kapanınca state'i sıfırla (sonraki açılış temiz başlasın).
  useEffect(() => {
    if (!open) {
      setStage("compose");
      setQuery("");
      setPreview(null);
      setResult(null);
      setError(null);
      setBusy(false);
    }
  }, [open]);

  const handleAsk = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await askCopilot(trimmed, false);
      setPreview(resp);
      setStage("preview");
    } catch (e) {
      setError(toUserError(e));
      setStage("error");
    } finally {
      setBusy(false);
    }
  }, [query]);

  const handleConfirm = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    setStage("executing");
    try {
      const resp = await askCopilot(trimmed, true);
      setResult(resp);
      setStage("result");
    } catch (e) {
      setError(toUserError(e));
      setStage("error");
    } finally {
      setBusy(false);
    }
  }, [query]);

  const handleReset = useCallback(() => {
    setStage("compose");
    setPreview(null);
    setResult(null);
    setError(null);
  }, []);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            AI&apos;ya danış
          </DialogTitle>
          <DialogDescription>
            Doğal dilde sor — sistem önce hangi SQL&apos;in çalışacağını
            gösterir, sen onayla, sonra çalışır.
          </DialogDescription>
        </DialogHeader>

        {(stage === "compose" || stage === "preview") && (
          <ComposeView
            query={query}
            onChangeQuery={setQuery}
            busy={busy}
            preview={preview}
            stage={stage}
          />
        )}

        {stage === "executing" && <ExecutingView />}

        {stage === "result" && result && <ResultView response={result} />}

        {stage === "error" && error && <ErrorView error={error} />}

        <DialogFooter>
          {stage === "compose" && (
            <Button onClick={handleAsk} disabled={busy || !query.trim()}>
              {busy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Sor
            </Button>
          )}
          {stage === "preview" && (
            <>
              <Button variant="ghost" onClick={handleReset} disabled={busy}>
                Yeni soru
              </Button>
              <Button onClick={handleConfirm} disabled={busy}>
                <ShieldCheck className="mr-2 h-4 w-4" />
                Onayla ve çalıştır
              </Button>
            </>
          )}
          {(stage === "result" || stage === "error") && (
            <Button onClick={handleReset}>Yeni soru</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ComposeView({
  query,
  onChangeQuery,
  busy,
  preview,
  stage,
}: {
  query: string;
  onChangeQuery: (v: string) => void;
  busy: boolean;
  preview: CopilotResponse | null;
  stage: Stage;
}) {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Soru
        </label>
        <Textarea
          value={query}
          onChange={(e) => onChangeQuery(e.target.value)}
          placeholder="Örn: Geçen ay AcmeCo'ya kaç fatura kestik?"
          rows={3}
          disabled={busy}
          className="mt-1"
        />
      </div>

      {stage === "preview" && preview && (
        <PreviewPanel response={preview} />
      )}
    </div>
  );
}

function PreviewPanel({ response }: { response: CopilotResponse }) {
  const intent = response.intent.intent;
  const showSql = response.sql !== null;
  return (
    <div className="space-y-3 rounded-md border border-border bg-muted/30 p-3">
      <div className="flex items-center gap-2">
        <Badge tone="info">intent: {intent}</Badge>
        {response.sql_template_used && (
          <Badge tone="neutral">
            template: {response.sql_template_used}
          </Badge>
        )}
      </div>
      <p className="text-sm text-muted-foreground">{response.summary_text}</p>
      {showSql && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            Çalışacak SQL
          </div>
          <pre className="overflow-x-auto rounded bg-background/50 p-2 font-mono text-[11px] text-foreground">
            {response.sql}
          </pre>
          {response.params.length > 0 && (
            <div className="mt-2">
              <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                Parametreler
              </div>
              <pre className="overflow-x-auto rounded bg-background/50 p-2 font-mono text-[11px] text-foreground">
                {JSON.stringify(response.params)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ExecutingView() {
  return (
    <div className="flex items-center gap-2 rounded-md border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      Sorgu çalışıyor…
    </div>
  );
}

function ResultView({ response }: { response: CopilotResponse }) {
  const rows = response.results;
  const columns = inferColumns(rows);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Badge tone="success">Sonuç</Badge>
        <span className="text-sm text-foreground">{response.summary_text}</span>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">Kayıt bulunamadı.</p>
      ) : (
        <div className="max-h-[40vh] overflow-y-auto">
          <DataTable
            columns={columns}
            rows={rows}
            rowId={(r) => String((r as { id?: unknown }).id ?? Math.random())}
            pageSize={10}
          />
        </div>
      )}
    </div>
  );
}

function ErrorView({
  error,
}: {
  error: { title: string; detail: string };
}) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
      <div>
        <div className="font-medium text-foreground">{error.title}</div>
        <div className="text-xs text-muted-foreground">{error.detail}</div>
      </div>
    </div>
  );
}

function inferColumns(
  rows: Array<Record<string, unknown>>,
): ColumnDef<Record<string, unknown>>[] {
  if (rows.length === 0) return [];
  const keys = Object.keys(rows[0]);
  return keys.map((k) => ({
    id: k,
    label: k,
    sortKey: (r) => {
      const v = r[k];
      if (typeof v === "number" || typeof v === "string") return v;
      return null;
    },
    cell: (r) => formatCell(r[k]),
  }));
}

function formatCell(v: unknown): React.ReactNode {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return v.toLocaleString("tr-TR");
  if (typeof v === "boolean") return v ? "✓" : "—";
  return String(v);
}

function toUserError(e: unknown): { title: string; detail: string } {
  if (e instanceof ApiError) {
    if (e.status === 429) {
      return {
        title: "Çok sık sorgu",
        detail:
          "AI'ya çok hızlı soru gönderildi. Bir dakika sonra tekrar deneyin.",
      };
    }
    if (e.status === 403) {
      return {
        title: "Yetki yok",
        detail: "Bu sorgu için yetkiniz yok.",
      };
    }
    if (e.status === 400) {
      return {
        title: "Sorgu reddedildi",
        detail: detailMessage(e.detail) ?? "Salt-okunur kısıtlaması.",
      };
    }
    return {
      title: "Sorgu işlenemedi",
      detail: detailMessage(e.detail) ?? "Tekrar deneyin.",
    };
  }
  return { title: "Beklenmeyen hata", detail: "Tekrar deneyin." };
}

function detailMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (
    detail &&
    typeof detail === "object" &&
    "detail" in detail &&
    typeof (detail as { detail: unknown }).detail === "string"
  ) {
    return (detail as { detail: string }).detail;
  }
  return null;
}
