"use client";

/**
 * M1 — UI Gallery (token binding görsel kanıtı).
 *
 * Tüm yeni bileşenler 3 modül (aq/finos/corpos) bağlamında render edilir.
 * data-module sayfada üst seviyede değiştirilir → tüm bileşenler aynı semantic
 * class'ları kullandığı için modül cascade otomatik yansır (turkuaz / altın /
 * azure). Light/dark eksenini de bu sayfada toggle ile gözle kanıtlarız.
 */
import { useEffect, useState } from "react";
import { Search, Settings, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Combobox } from "@/components/ui/combobox";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { toast } from "@/components/ui/toast";
import { DatePicker } from "@/components/ui/date-picker";
import { DataTable, type ColumnDef } from "@/components/ui/data-table";
import { setThemeCookie } from "@/lib/theme";

type Module = "aq" | "finos" | "corpos";
type Theme = "dark" | "light";

interface DemoRow {
  id: string;
  company: string;
  amount: number;
  status: "ok" | "pending" | "fail";
  date: string;
}

const DEMO_ROWS: DemoRow[] = [
  { id: "r1", company: "Acme Tekstil", amount: 45230, status: "ok", date: "2026-05-12" },
  { id: "r2", company: "Beta Metal", amount: 12800, status: "pending", date: "2026-05-15" },
  { id: "r3", company: "Gamma Lojistik", amount: 78420, status: "ok", date: "2026-05-18" },
  { id: "r4", company: "Delta Yapı", amount: 3300, status: "fail", date: "2026-05-21" },
  { id: "r5", company: "Epsilon Gıda", amount: 23600, status: "ok", date: "2026-05-25" },
];

const TABLE_COLUMNS: ColumnDef<DemoRow>[] = [
  { id: "company", label: "Şirket", cell: (r) => r.company, sortKey: (r) => r.company },
  { id: "amount", label: "Tutar", cell: (r) => `₺${r.amount.toLocaleString("tr-TR")}`, sortKey: (r) => r.amount },
  { id: "status", label: "Durum", cell: (r) => (
      <Badge tone={r.status === "ok" ? "success" : r.status === "pending" ? "warn" : "critical"}>
        {r.status}
      </Badge>
    ), sortKey: (r) => r.status },
  { id: "date", label: "Tarih", cell: (r) => r.date, sortKey: (r) => r.date },
];

const SELECT_ITEMS = [
  { value: "ok", label: "Onaylı" },
  { value: "pending", label: "Beklemede" },
  { value: "fail", label: "Reddedildi" },
];

const COMBO_ITEMS = [
  { value: "tr", label: "Türkiye" },
  { value: "de", label: "Almanya" },
  { value: "fr", label: "Fransa" },
  { value: "uk", label: "Birleşik Krallık" },
];

export default function UiGallery() {
  const [module, setModule] = useState<Module>("aq");
  const [theme, setTheme] = useState<Theme>("dark");
  const [date, setDate] = useState<Date | undefined>();
  const [country, setCountry] = useState<string>("");
  const [status, setStatus] = useState<string>("ok");
  const [notify, setNotify] = useState(true);

  // data-module + data-theme sayfada lokal olarak override edilir (en kolay
  // canlı önizleme; üretim cascade'i için layout'un set ettiği değerler vardır).
  useEffect(() => {
    document.documentElement.dataset.module = module;
    document.documentElement.dataset.theme = theme;
    if (theme === "light") document.documentElement.classList.add("light");
    else document.documentElement.classList.remove("light");
    setThemeCookie(theme);
  }, [module, theme]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="container mx-auto py-8 space-y-6">
        <header className="space-y-2">
          <h1 className="text-3xl font-bold">UI Gallery</h1>
          <p className="text-sm text-muted-foreground">
            M1 token-bağlı bileşenler. Modül + tema değiştir → her bileşen aynı
            semantic token&apos;larla otomatik cascade&apos;lenir.
          </p>
          <div className="flex flex-wrap gap-2 pt-2">
            <div className="flex gap-1 rounded-md border border-border bg-card p-1">
              {(["aq", "finos", "corpos"] as Module[]).map((m) => (
                <Button
                  key={m}
                  variant={module === m ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => setModule(m)}
                >
                  {m}
                </Button>
              ))}
            </div>
            <div className="flex gap-1 rounded-md border border-border bg-card p-1">
              {(["dark", "light"] as Theme[]).map((t) => (
                <Button
                  key={t}
                  variant={theme === t ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => setTheme(t)}
                >
                  {t}
                </Button>
              ))}
            </div>
          </div>
        </header>

        {/* Forms */}
        <Card>
          <CardHeader>
            <CardTitle>Form kontrolleri</CardTitle>
            <CardDescription>Label / Input / Textarea / Checkbox / Radio / Switch / Select / Combobox / DatePicker</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="g-input">İsim</Label>
              <Input id="g-input" placeholder="örn. Mustafa" leadingIcon={<Search className="h-4 w-4" />} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="g-textarea">Açıklama</Label>
              <Textarea id="g-textarea" placeholder="Notlar…" />
            </div>
            <div className="space-y-2">
              <Label>Durum</Label>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SELECT_ITEMS.map((it) => (
                    <SelectItem key={it.value} value={it.value}>{it.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Ülke (combobox)</Label>
              <Combobox items={COMBO_ITEMS} value={country} onChange={setCountry} placeholder="Ülke seç…" />
            </div>
            <div className="space-y-2">
              <Label>Tarih</Label>
              <DatePicker value={date} onChange={setDate} />
            </div>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Checkbox id="g-cb" defaultChecked />
                <Label htmlFor="g-cb">Şartları kabul ediyorum</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch id="g-sw" checked={notify} onCheckedChange={setNotify} />
                <Label htmlFor="g-sw">Bildirim al</Label>
              </div>
              <RadioGroup defaultValue="a" className="flex gap-4">
                <div className="flex items-center gap-2"><RadioGroupItem id="ra" value="a" /><Label htmlFor="ra">Aylık</Label></div>
                <div className="flex items-center gap-2"><RadioGroupItem id="rb" value="b" /><Label htmlFor="rb">Yıllık</Label></div>
              </RadioGroup>
            </div>
          </CardContent>
        </Card>

        {/* Overlays */}
        <Card>
          <CardHeader>
            <CardTitle>Overlay&apos;ler</CardTitle>
            <CardDescription>Popover / Dropdown menu / Sheet / Toast</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-2">
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline">Popover</Button>
              </PopoverTrigger>
              <PopoverContent>
                <p className="text-sm">Popover içeriği — token-bağlı yüzey ve metin.</p>
              </PopoverContent>
            </Popover>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline"><Settings className="h-4 w-4" />Dropdown</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuLabel>Aksiyonlar</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Düzenle</DropdownMenuItem>
                <DropdownMenuItem>Kopyala</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem>
                  <Trash2 className="h-4 w-4" /> Sil
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline">Sheet / Drawer</Button>
              </SheetTrigger>
              <SheetContent>
                <SheetHeader>
                  <SheetTitle>Yan panel</SheetTitle>
                  <SheetDescription>Token-bağlı yüzey, modül cascade&apos;i.</SheetDescription>
                </SheetHeader>
                <p className="pt-4 text-sm text-muted-foreground">İçerik buraya gelir.</p>
              </SheetContent>
            </Sheet>

            <Button variant="secondary" onClick={() => toast.success("Toast tetiklendi", { description: "Sonner sarmal — modül-bağlı renkler" })}>
              Toast
            </Button>
          </CardContent>
        </Card>

        {/* Data table */}
        <Card>
          <CardHeader>
            <CardTitle>DataTable</CardTitle>
            <CardDescription>Sıralama (sütun başlığı) + sütun göster/gizle + satır seçimi + sayfalama + dışa aktar kancası</CardDescription>
          </CardHeader>
          <CardContent>
            <DataTable
              columns={TABLE_COLUMNS}
              rows={DEMO_ROWS}
              rowId={(r) => r.id}
              pageSize={3}
              onExport={(rows) => toast.info(`${rows.length} satır seçildi (export hook)`)}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
