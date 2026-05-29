"use client";

/**
 * A4: AI Invoice OCR page — fiş/fatura fotoğrafı yükle → Claude Vision
 * extract → kullanıcı düzelt + onayla → ledger entry.
 */
import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  Loader2,
  Receipt,
  RefreshCw,
  Sparkles,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import {
  confirmOcrJob,
  listOcrJobs,
  uploadInvoiceImage,
  type OcrExtract,
  type OcrJob,
} from "@/lib/ocr-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/cn";


type EditableExtract = {
  vendor_name: string;
  invoice_no: string;
  issue_date: string;
  total_amount: string;
  direction: "outgoing" | "incoming";
  category: string;
};


function emptyForm(extract: OcrExtract): EditableExtract {
  return {
    vendor_name: extract.vendor_name ?? "",
    invoice_no: extract.invoice_no ?? "",
    issue_date: extract.issue_date ?? "",
    total_amount:
      extract.total_amount !== null && extract.total_amount !== undefined
        ? String(extract.total_amount)
        : "",
    direction: (extract.direction ?? "incoming") as "outgoing" | "incoming",
    category: extract.category ?? "diğer",
  };
}


export default function OcrPage() {
  const [job, setJob] = useState<OcrJob | null>(null);
  const [form, setForm] = useState<EditableExtract | null>(null);
  const [companyName, setCompanyName] = useState("Demo Holding A.Ş.");
  const [history, setHistory] = useState<OcrJob[]>([]);
  const [uploading, setUploading] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const loadHistory = useCallback(async () => {
    try {
      const list = await listOcrJobs(10);
      setHistory(list.jobs);
    } catch {
      setHistory([]);
    }
  }, []);

  useEffect(() => { void loadHistory(); }, [loadHistory]);

  async function handleFile(file: File) {
    if (!file.type.startsWith("image/")) {
      toast.error("Sadece görüntü dosyası");
      return;
    }
    setUploading(true);
    try {
      const result = await uploadInvoiceImage(file);
      setJob(result);
      setForm(emptyForm(result.extract));
      toast.success("OCR tamamlandı 🎯", {
        description: `%${result.confidence_pct.toFixed(0)} güven`,
      });
    } catch (err) {
      toast.error("OCR başarısız", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setUploading(false);
    }
  }

  async function handleConfirm() {
    if (!job || !form) return;
    setConfirming(true);
    try {
      const payload = {
        company_name: companyName.trim(),
        vendor_name: form.vendor_name || undefined,
        invoice_no: form.invoice_no || undefined,
        issue_date: form.issue_date || undefined,
        total_amount: form.total_amount ? Number(form.total_amount) : undefined,
        direction: form.direction,
        category: form.category || undefined,
      };
      const confirmed = await confirmOcrJob(job.id, payload);
      toast.success("Fatura ledger'a eklendi", {
        description: `Entry #${confirmed.ledger_entry_id}`,
      });
      setJob(null);
      setForm(null);
      await loadHistory();
    } catch (err) {
      toast.error("Onay başarısız", {
        description: err instanceof Error ? err.message : "Bilinmeyen hata",
      });
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <motion.header
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <Badge tone="primary" withDot>AI Fiş/Fatura Tarayıcı</Badge>
        <h1 className="text-2xl font-bold mt-2">
          Fotoğraf at,{" "}
          <span className="bg-gradient-to-r from-aq-quantum-2 to-aq-plasma bg-clip-text text-transparent">
            ledger doldu
          </span>
        </h1>
        <p className="text-sm text-aq-dust mt-1">
          Fiş veya fatura fotoğrafını yükle. Claude Vision otomatik olarak
          tedarikçi, tarih, tutar ve kategori çıkarır.
        </p>
      </motion.header>

      {/* Upload zone */}
      {!job && (
        <Card variant="glass" className="p-6">
          <UploadZone onFile={handleFile} uploading={uploading} />
        </Card>
      )}

      {/* Extract form */}
      {job && form && (
        <Card variant="glass" className="p-6">
          <CardHeader className="p-0 pb-3 flex-row items-start justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-aq-quantum-2" />
                OCR Sonucu
              </CardTitle>
              <CardDescription>
                Çıkarılan field'ları kontrol et, gerekirse düzelt, onayla.
                Onaylandığında ledger entry oluşur.
              </CardDescription>
            </div>
            <Badge
              tone={
                job.confidence_pct >= 85 ? "success" :
                job.confidence_pct >= 70 ? "warn" : "critical"
              }
            >
              %{job.confidence_pct.toFixed(0)} güven
            </Badge>
          </CardHeader>
          <CardContent className="p-0 space-y-3">
            {job.extract.notes && (
              <div className="rounded-md border border-aq-mist/30 bg-aq-cosmos/40 p-2 text-[11px] text-aq-dust">
                💡 {job.extract.notes}
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <FormField label="Tedarikçi" value={form.vendor_name} onChange={(v) => setForm({ ...form, vendor_name: v })} />
              <FormField label="Fatura No" value={form.invoice_no} onChange={(v) => setForm({ ...form, invoice_no: v })} />
              <FormField label="Tarih (YYYY-MM-DD)" value={form.issue_date} onChange={(v) => setForm({ ...form, issue_date: v })} placeholder="2026-05-15" />
              <FormField label="Tutar (₺)" value={form.total_amount} onChange={(v) => setForm({ ...form, total_amount: v })} type="number" />
              <SelectField
                label="Yön"
                value={form.direction}
                onChange={(v) => setForm({ ...form, direction: v as "outgoing" | "incoming" })}
                options={[
                  { value: "incoming", label: "Gider (alış)" },
                  { value: "outgoing", label: "Gelir (satış)" },
                ]}
              />
              <FormField label="Kategori" value={form.category} onChange={(v) => setForm({ ...form, category: v })} />
              <FormField label="Şirket" value={companyName} onChange={setCompanyName} />
            </div>
            <div className="flex justify-end gap-2 pt-3 border-t border-aq-mist/30">
              <Button variant="ghost" size="sm" onClick={() => { setJob(null); setForm(null); }}>
                İptal
              </Button>
              <Button onClick={handleConfirm} disabled={confirming || !companyName.trim()}>
                {confirming ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    Onaylanıyor…
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
                    Onayla ve Ledger'a Ekle
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* History */}
      <Card variant="glass" className="p-6">
        <CardHeader className="p-0 pb-3 flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Receipt className="h-4 w-4 text-aq-dust" />
              Son OCR Geçmişi
            </CardTitle>
          </div>
          <Button variant="ghost" size="sm" onClick={() => void loadHistory()}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {history.length === 0 && (
            <p className="text-xs text-aq-dust text-center py-4">Henüz OCR yok.</p>
          )}
          <div className="space-y-2">
            {history.map((h) => (
              <div key={h.id} className="rounded-md border border-aq-mist/40 bg-aq-orbital/40 p-3 text-xs">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge tone={
                    h.status === "confirmed" ? "success" :
                    h.status === "extracted" ? "warn" :
                    h.status === "failed" ? "critical" : "neutral"
                  }>
                    {h.status}
                  </Badge>
                  <span className="font-medium">{h.extract.vendor_name || "—"}</span>
                  {h.extract.total_amount != null && (
                    <span className="font-mono">{h.extract.total_amount.toLocaleString("tr-TR")} ₺</span>
                  )}
                  <span className="ml-auto text-[10px] text-aq-trace">
                    {new Date(h.created_at * 1000).toLocaleString("tr-TR")}
                  </span>
                </div>
                <p className="text-[10px] text-aq-trace mt-1">
                  {h.source_filename || "—"} · {h.extract.category} · %{h.confidence_pct.toFixed(0)}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


function UploadZone({
  onFile,
  uploading,
}: {
  onFile: (f: File) => void;
  uploading: boolean;
}) {
  return (
    <label className={cn(
      "block rounded-lg border-2 border-dashed p-10 text-center cursor-pointer transition-colors",
      uploading ? "border-aq-quantum/40 bg-aq-quantum/5" : "border-aq-mist/40 bg-aq-cosmos/40 hover:border-aq-mist/60",
    )}>
      <input
        type="file"
        accept="image/*"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
        className="hidden"
        disabled={uploading}
      />
      {uploading ? (
        <>
          <Loader2 className="h-10 w-10 mx-auto mb-3 text-aq-quantum-2 animate-spin" />
          <p className="text-sm font-medium text-foreground">Claude Vision çalışıyor…</p>
          <p className="text-[11px] text-aq-trace mt-1">Genellikle 5-10 saniye</p>
        </>
      ) : (
        <>
          <Upload className="h-10 w-10 mx-auto mb-3 text-aq-dust" />
          <p className="text-sm font-medium text-foreground">Fiş veya fatura fotoğrafı yükle</p>
          <p className="text-[11px] text-aq-trace mt-1">JPG / PNG / WebP · Max 10 MB</p>
        </>
      )}
    </label>
  );
}


function FormField({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wider text-aq-trace block mb-1">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-aq-mist/40 bg-aq-orbital/60 px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:border-aq-quantum/40"
      />
    </div>
  );
}


function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wider text-aq-trace block mb-1">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-aq-mist/40 bg-aq-orbital/60 px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:border-aq-quantum/40"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  );
}
