"use client";

/**
 * M2 — Generic liste sayfası iskelet bileşeni.
 *
 * Modül sayfası şablonunun çekirdeği:
 *   - Sayfa header (başlık + açıklama + birincil aksiyon)
 *   - Arama / filtre çubuğu
 *   - Liste alanı: data-table (boş/yükleniyor/hata) — kullanıcı kendi kolonlarını verir
 *   - Hata: text-destructive banner + reload butonu
 *
 * Kullanım pattern'ı /procurement/page.tsx, /finance/page.tsx, /feasibility/page.tsx.
 */
import { useMemo, useState } from "react";
import { Search, RotateCcw, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import type { UseResourceResult } from "@/lib/use-resource";

export interface ResourceListPageProps<T> {
  title: string;
  description?: string;
  columns: ColumnDef<T>[];
  rowId: (row: T) => string;
  resource: UseResourceResult<{ records: T[]; total?: number }>;
  /** Arama filtresi — verilen satır metinler üzerinden lokal filtre. */
  searchFields?: (row: T) => string;
  searchPlaceholder?: string;
  /** Birincil aksiyon (örn. "Yeni RFQ"). */
  primaryAction?: { label: string; onClick: () => void; icon?: React.ReactNode };
  /** Dışa aktar kancası (data-table'a iletilir). */
  onExport?: (rows: T[]) => void;
  pageSize?: number;
  emptyMessage?: string;
}

export function ResourceListPage<T>({
  title,
  description,
  columns,
  rowId,
  resource,
  searchFields,
  searchPlaceholder = "Ara…",
  primaryAction,
  onExport,
  pageSize = 25,
  emptyMessage,
}: ResourceListPageProps<T>) {
  const [query, setQuery] = useState("");
  const records = resource.data?.records ?? [];

  const filtered = useMemo(() => {
    if (!searchFields || !query.trim()) return records;
    const q = query.toLowerCase();
    return records.filter((r) => searchFields(r).toLowerCase().includes(q));
  }, [records, query, searchFields]);

  return (
    <div className="space-y-4 animate-fade-in">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{title}</h1>
          {description && (
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          )}
          <p className="mt-1 text-[11px] text-muted-foreground">
            {filtered.length} kayıt
            {resource.data?.total !== undefined &&
              resource.data.total !== filtered.length &&
              ` (toplam ${resource.data.total})`}
          </p>
        </div>
        {primaryAction && (
          <Button onClick={primaryAction.onClick}>
            {primaryAction.icon ?? <Plus className="h-4 w-4" />}
            {primaryAction.label}
          </Button>
        )}
      </header>

      {/* Filtre çubuğu */}
      {searchFields && (
        <Card>
          <CardContent className="flex flex-wrap items-center gap-2 p-3">
            <div className="flex-1 min-w-64">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={searchPlaceholder}
                leadingIcon={<Search className="h-4 w-4" />}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Hata durumu */}
      {resource.error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive"
        >
          <span>{resource.error.message}</span>
          <Button variant="ghost" size="sm" onClick={resource.reload}>
            <RotateCcw className="h-3.5 w-3.5" />
            Tekrar dene
          </Button>
        </div>
      )}

      {/* Tablo */}
      <DataTable
        columns={columns}
        rows={filtered}
        rowId={rowId}
        loading={resource.loading}
        emptyMessage={emptyMessage}
        pageSize={pageSize}
        onExport={onExport}
      />
    </div>
  );
}
