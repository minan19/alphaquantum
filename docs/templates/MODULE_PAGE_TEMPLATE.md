# Modül Sayfası Şablonu (M2)

Bu doküman, **yeni bir modülü** Alpha Quantum frontend'ine 4-5 dosyalık standart şablonla eklemeyi anlatır. Tüm M2 sayfaları (procurement, finance, feasibility) bu desene göre yazılmıştır.

## Temel Bloklar

| Sorumluluk | Yer |
|---|---|
| Tipler + fetch fonksiyonları | `frontend/lib/<modül>-api.ts` |
| Veri kancası (fetch + loading + error) | `frontend/lib/use-resource.ts` (mevcut) |
| Generic liste sayfası iskelet | `frontend/components/module/ResourceListPage.tsx` (mevcut) |
| Generic detay başlığı | `frontend/components/module/ResourceDetailHeader.tsx` (mevcut) |
| Liste sayfası | `frontend/app/(app)/<modül>/page.tsx` |
| Detay sayfası | `frontend/app/(app)/<modül>/[id]/page.tsx` |

## Hızlı Reçete (≈100 satır toplam)

### 1) API client — `lib/<modül>-api.ts`

```ts
import { apiRequest } from "@/lib/api";

export interface MyResource { id: number; title: string; status: string; }
export interface MyResourceListResponse { total: number; records: MyResource[]; }

export function listMyResource(params?: { limit?: number }): Promise<MyResourceListResponse> {
  return apiRequest("/api/v1/my-resource", { params });
}
export function getMyResource(id: number): Promise<MyResource> {
  return apiRequest(`/api/v1/my-resource/${id}`);
}
```

### 2) Liste sayfası — `app/(app)/<modül>/page.tsx`

```tsx
"use client";
import { useCallback } from "react";
import { ResourceListPage } from "@/components/module/ResourceListPage";
import { useResource } from "@/lib/use-resource";
import { listMyResource, type MyResource } from "@/lib/my-resource-api";
import type { ColumnDef } from "@/components/ui/data-table";

const COLUMNS: ColumnDef<MyResource>[] = [
  { id: "title", label: "Başlık", sortKey: (r) => r.title, cell: (r) => r.title },
  { id: "status", label: "Durum", sortKey: (r) => r.status, cell: (r) => r.status },
];

export default function MyResourceListPage() {
  const fetcher = useCallback(() => listMyResource({ limit: 500 }), []);
  const resource = useResource(fetcher);
  return (
    <ResourceListPage
      title="My Resource"
      columns={COLUMNS}
      rowId={(r) => String(r.id)}
      resource={resource}
      searchFields={(r) => `${r.title} ${r.status}`}
    />
  );
}
```

### 3) Detay sayfası — `app/(app)/<modül>/[id]/page.tsx`

```tsx
"use client";
import { use, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ResourceDetailHeader, ResourceDetailNotFound } from "@/components/module/ResourceDetailHeader";
import { useResource } from "@/lib/use-resource";
import { getMyResource } from "@/lib/my-resource-api";

export default function MyResourceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: idStr } = use(params);
  const fetcher = useCallback(() => getMyResource(Number(idStr)), [idStr]);
  const r = useResource(fetcher);
  if (r.loading) return <Skeleton className="h-64 w-full" />;
  if (r.error || !r.data) return <ResourceDetailNotFound resourceLabel="My Resource" backHref="/my-resource" />;
  return (
    <div className="space-y-6 animate-fade-in">
      <ResourceDetailHeader backHref="/my-resource" title={r.data.title} />
      <Card>
        <CardHeader><CardTitle>Detay</CardTitle></CardHeader>
        <CardContent>{r.data.status}</CardContent>
      </Card>
    </div>
  );
}
```

### 4) Sidebar'a link — `components/sidebar.tsx`

`NAV` listesindeki uygun gruba (CorpOS / FinOS / Hesap) bir satır ekle:

```ts
{ href: "/my-resource", label: "My Resource", icon: SomeLucideIcon, module: "corpos" },
```

### 5) Modül cascade — `lib/tokens.ts`

`detectModuleFromPathname` regex'ine route prefix'i ekle (modüle göre `corpos` veya `finos`):

```ts
if (/^\/(customers|companies|procurement|feasibility|my-resource)(\/|$)/.test(pathname)) {
  return "corpos";
}
```

## Performans notu (M2.3 ölçümü)

5000 satır sentetik veriyle (`/ui-gallery/perf`):

| İşlem | 5000 satır | 10000 satır |
|---|---:|---:|
| `generate` (data oluştur) | 1.9 ms | 3.5 ms |
| `sort` (number key) | 1.2 ms | 3.6 ms |
| `filter` (substring) | 0.4 ms | — |
| `slice (page size 100)` | 0.0 ms | — |

Hepsi **60fps budget (16.7ms) altında**. Karar: **client-side sıralama/filtre yeterli** — TanStack table / virtualization GEREKMİYOR. Modül listelerinde sunucu-taraflı pagination'a geçmek için eşik: tek liste >50k satır.

## Token cascade güvencesi

Sayfalar M1 bileşenlerinden (`Card`, `Button`, `Badge`, `DataTable`, vb.) inşa edilir. Bu bileşenler yalnız semantic class (`bg-primary`, `border-input`, `text-muted-foreground`, vb.) kullanır → `data-module` cascade'i otomatik:

- `/procurement` → CorpOS → primary altın
- `/feasibility` → CorpOS → primary altın
- `/finance` → FinOS → primary turuncu

Hex/hardcoded yok. Yeni modülde de değişiklik gerekmez.
