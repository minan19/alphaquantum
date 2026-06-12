"use client";

/**
 * Faz 5 — Snapshot History Drawer.
 *
 * Aktif scope için snapshot listesi (yeni→eski). Her satır:
 *  - Etiket + kaynak rozeti (pre_save / pre_reset / pre_restore / manual)
 *  - Zaman damgası
 *  - "Bu noktaya dön" butonu (restore)
 *
 * Restore'un kendisi de pre_restore snapshot bıraktığı için kullanıcı dilediği
 * kadar geri-ileri sarabilir. Drawer kapanır kapanmaz parent reload tetiklenir.
 */
import { useCallback, useEffect, useState } from "react";
import { Loader2, RotateCcw, X, History } from "lucide-react";
import {
  listSnapshots,
  restoreSnapshot,
  type SnapshotSummary,
  type SnapshotSource,
} from "@/lib/design-tokens-api";
import type { Scope } from "@/lib/tokens";

const SOURCE_LABELS: Record<SnapshotSource, string> = {
  pre_save: "Otomatik · kaydetme öncesi",
  pre_reset: "Otomatik · fabrika öncesi",
  pre_restore: "Otomatik · geri sarma öncesi",
  manual: "Manuel kayıt",
};

const SOURCE_TONES: Record<SnapshotSource, string> = {
  pre_save: "bg-aq-quantum/15 text-aq-quantum-2",
  pre_reset: "bg-aq-fission/15 text-aq-fission",
  pre_restore: "bg-aq-solar/15 text-aq-solar",
  manual: "bg-aq-fusion/15 text-aq-fusion",
};

function formatTimestamp(unixSec: number): string {
  if (!unixSec) return "—";
  const d = new Date(unixSec * 1000);
  return d.toLocaleString("tr-TR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function SnapshotHistoryDrawer({
  scope,
  open,
  onClose,
  onRestored,
}: {
  scope: Scope;
  open: boolean;
  onClose: () => void;
  onRestored: () => void;
}) {
  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!open) return;
    setLoading(true);
    setError(null);
    try {
      const res = await listSnapshots(scope, 50);
      setSnapshots(res.snapshots);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Geçmiş yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [open, scope]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const handleRestore = useCallback(
    async (snapshotId: number) => {
      setBusyId(snapshotId);
      setError(null);
      try {
        await restoreSnapshot(snapshotId);
        onRestored();
        await reload();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Geri sarma başarısız");
      } finally {
        setBusyId(null);
      }
    },
    [onRestored, reload],
  );

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      {/* Drawer */}
      <aside
        className="fixed top-0 right-0 z-50 h-screen w-full max-w-md overflow-y-auto border-l border-aq-mist/40 bg-aq-cosmos shadow-elevation-3"
        role="dialog"
        aria-label="Snapshot geçmişi"
      >
        <header className="flex items-start justify-between border-b border-aq-mist/40 px-5 py-4">
          <div>
            <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-aq-trace">
              <History className="h-3.5 w-3.5" /> Faz 5 · Geçmiş
            </div>
            <h2 className="mt-1 text-lg font-semibold">
              {scope.toUpperCase()} snapshot zinciri
            </h2>
            <p className="mt-0.5 text-xs text-aq-dust">
              Her kayıt öncesi otomatik snapshot alınır. Geri dönüşler de
              yeni snapshot bırakır — kaybolan bir adım yok.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1.5 text-aq-dust hover:bg-aq-mist/40"
            aria-label="Kapat"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="px-5 py-4">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-aq-dust">
              <Loader2 className="h-4 w-4 animate-spin" /> Yükleniyor…
            </div>
          )}

          {error && (
            <div className="rounded-md border border-aq-fission/40 bg-aq-fission/10 px-3 py-2 text-xs text-aq-fission">
              {error}
            </div>
          )}

          {!loading && !error && snapshots.length === 0 && (
            <div className="rounded-md border border-aq-mist/40 bg-aq-orbital/30 px-4 py-6 text-center text-sm text-aq-dust">
              Henüz snapshot yok. İlk kaydı yaptığında burada görünecek.
            </div>
          )}

          <ul className="space-y-2">
            {snapshots.map((snap) => (
              <li
                key={snap.id}
                className="rounded-md border border-aq-mist/30 bg-aq-orbital/40 px-3 py-3 transition hover:border-aq-quantum/40"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[9px] uppercase tracking-wider ${SOURCE_TONES[snap.source]}`}
                      >
                        {snap.source}
                      </span>
                      <span className="font-mono text-[10px] text-aq-trace">
                        #{snap.id}
                      </span>
                    </div>
                    <div className="mt-1 truncate text-sm text-aq-neutron">
                      {snap.label}
                    </div>
                    <div className="mt-0.5 text-[11px] text-aq-dust">
                      {formatTimestamp(snap.taken_at)} ·{" "}
                      <span className="text-aq-trace">
                        {SOURCE_LABELS[snap.source]}
                      </span>
                      {snap.created_by && (
                        <span className="ml-1 text-aq-trace">· {snap.created_by}</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleRestore(snap.id)}
                    disabled={busyId !== null}
                    className="inline-flex shrink-0 items-center gap-1 rounded-md border border-aq-quantum/40 px-2 py-1 text-xs text-aq-quantum-2 transition hover:bg-aq-quantum/10 disabled:opacity-40"
                    title="Bu noktaya dön"
                  >
                    {busyId === snap.id ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <RotateCcw className="h-3 w-3" />
                    )}
                    Bu noktaya dön
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </>
  );
}
