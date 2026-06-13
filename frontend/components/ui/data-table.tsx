"use client";

/**
 * M1 — DataTable: ERP tablolarının temel yapı taşı.
 *
 * Özellikler (TanStack table bağımlılığı YOK — saf React):
 *   - Sıralama (asc/desc/none) — sütun başlığına tıkla
 *   - Sütun göster/gizle (dropdown)
 *   - Satır seçimi (checkbox + tümünü seç)
 *   - Sayfalama (pageSize prop)
 *   - Boş/yükleniyor durumları
 *   - Dışa aktar kancası (onExport: seçili veya tüm satırlar)
 *
 * Tüm class'lar semantic token üzerinden — modül cascade ve light/dark
 * tema otomatik.
 */
import * as React from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, Download } from "lucide-react";
import { cn } from "@/lib/cn";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";

export interface ColumnDef<T> {
  /** Sütun benzersiz id'si — header text de bu olur (label override edilebilir). */
  id: string;
  label: string;
  /** Hücre render — null/undefined ise "—". */
  cell: (row: T) => React.ReactNode;
  /** Sıralama için string/number değer. Yoksa sıralanmaz. */
  sortKey?: (row: T) => string | number | null | undefined;
  /** Sütun başlangıçta görünür mü? Default true. */
  defaultVisible?: boolean;
  /** Hücre className. */
  className?: string;
}

export interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  rows: T[];
  /** Satır kimliği (key + seçim). */
  rowId: (row: T) => string;
  loading?: boolean;
  emptyMessage?: string;
  pageSize?: number;
  /** Dışa aktar — seçili varsa onlar, yoksa tüm filtreli satırlar. */
  onExport?: (rows: T[]) => void;
  className?: string;
}

type SortDir = "asc" | "desc" | null;

export function DataTable<T>({
  columns,
  rows,
  rowId,
  loading,
  emptyMessage = "Kayıt yok.",
  pageSize = 10,
  onExport,
  className,
}: DataTableProps<T>) {
  const [sortId, setSortId] = React.useState<string | null>(null);
  const [sortDir, setSortDir] = React.useState<SortDir>(null);
  const [page, setPage] = React.useState(0);
  const [hidden, setHidden] = React.useState<Set<string>>(
    () => new Set(columns.filter((c) => c.defaultVisible === false).map((c) => c.id)),
  );
  const [selected, setSelected] = React.useState<Set<string>>(new Set());

  const visibleColumns = columns.filter((c) => !hidden.has(c.id));

  const sortedRows = React.useMemo(() => {
    if (!sortId || !sortDir) return rows;
    const col = columns.find((c) => c.id === sortId);
    if (!col?.sortKey) return rows;
    const dir = sortDir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = col.sortKey!(a);
      const bv = col.sortKey!(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
  }, [rows, sortId, sortDir, columns]);

  const pageCount = Math.max(1, Math.ceil(sortedRows.length / pageSize));
  const pageRows = sortedRows.slice(page * pageSize, page * pageSize + pageSize);

  const allOnPageSelected =
    pageRows.length > 0 && pageRows.every((r) => selected.has(rowId(r)));

  const togglePageAll = () => {
    setSelected((cur) => {
      const next = new Set(cur);
      if (allOnPageSelected) {
        pageRows.forEach((r) => next.delete(rowId(r)));
      } else {
        pageRows.forEach((r) => next.add(rowId(r)));
      }
      return next;
    });
  };

  const toggleRow = (id: string) => {
    setSelected((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSort = (id: string) => {
    if (sortId !== id) {
      setSortId(id);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      setSortId(null);
      setSortDir(null);
    }
  };

  const handleExport = () => {
    if (!onExport) return;
    const selectedRows =
      selected.size > 0
        ? sortedRows.filter((r) => selected.has(rowId(r)))
        : sortedRows;
    onExport(selectedRows);
  };

  return (
    <div className={cn("space-y-3", className)}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-muted-foreground">
          {selected.size > 0
            ? `${selected.size} seçili · ${rows.length} satırdan`
            : `${rows.length} satır`}
        </div>
        <div className="flex items-center gap-2">
          {onExport && (
            <Button variant="outline" size="sm" onClick={handleExport}>
              <Download className="h-3.5 w-3.5" />
              Dışa aktar
            </Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                Sütunlar <ChevronDown className="h-3.5 w-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Görünür sütunlar</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {columns.map((c) => (
                <DropdownMenuCheckboxItem
                  key={c.id}
                  checked={!hidden.has(c.id)}
                  onCheckedChange={(checked) => {
                    setHidden((cur) => {
                      const next = new Set(cur);
                      if (checked) next.delete(c.id);
                      else next.add(c.id);
                      return next;
                    });
                  }}
                >
                  {c.label}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border border-border bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left">
              <th className="w-9 px-3 py-2">
                <Checkbox
                  checked={allOnPageSelected}
                  onCheckedChange={togglePageAll}
                  aria-label="Sayfadaki tüm satırları seç"
                />
              </th>
              {visibleColumns.map((c) => {
                const active = sortId === c.id && sortDir !== null;
                return (
                  <th
                    key={c.id}
                    className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    {c.sortKey ? (
                      <button
                        type="button"
                        onClick={() => onSort(c.id)}
                        className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
                      >
                        {c.label}
                        {!active && <ArrowUpDown className="h-3 w-3 opacity-40" />}
                        {active && sortDir === "asc" && <ArrowUp className="h-3 w-3" />}
                        {active && sortDir === "desc" && <ArrowDown className="h-3 w-3" />}
                      </button>
                    ) : (
                      c.label
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={visibleColumns.length + 1} className="px-3 py-8 text-center text-sm text-muted-foreground">
                  Yükleniyor…
                </td>
              </tr>
            )}
            {!loading && pageRows.length === 0 && (
              <tr>
                <td colSpan={visibleColumns.length + 1} className="px-3 py-8 text-center text-sm text-muted-foreground">
                  {emptyMessage}
                </td>
              </tr>
            )}
            {!loading &&
              pageRows.map((r) => {
                const id = rowId(r);
                const isSel = selected.has(id);
                return (
                  <tr
                    key={id}
                    className={cn(
                      "border-b border-border/50 transition-colors hover:bg-accent/40",
                      isSel && "bg-accent/30",
                    )}
                  >
                    <td className="w-9 px-3 py-2">
                      <Checkbox
                        checked={isSel}
                        onCheckedChange={() => toggleRow(id)}
                        aria-label="Satırı seç"
                      />
                    </td>
                    {visibleColumns.map((c) => (
                      <td key={c.id} className={cn("px-3 py-2 text-foreground", c.className)}>
                        {c.cell(r) ?? <span className="text-muted-foreground">—</span>}
                      </td>
                    ))}
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pageCount > 1 && (
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              />
            </PaginationItem>
            {Array.from({ length: pageCount }, (_, i) => (
              <PaginationItem key={i}>
                <PaginationLink isActive={page === i} onClick={() => setPage(i)}>
                  {i + 1}
                </PaginationLink>
              </PaginationItem>
            ))}
            <PaginationItem>
              <PaginationNext
                onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                disabled={page === pageCount - 1}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      )}
    </div>
  );
}
