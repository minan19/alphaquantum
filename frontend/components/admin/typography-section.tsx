"use client";

/**
 * Faz 6 — Tipografi paneli (Tasarım Tokenları sayfasında bölüm).
 *
 * Aktif scope için:
 *   - Google Fonts: aile adı + ağırlık seçim + Ekle
 *   - Upload: .woff2/.woff/.ttf/.otf + format seç + Yükle
 *   - Mevcut fontlar listesi: ★ Varsayılan, 🗑 Sil, "Önizleme"
 *
 * Default font seçilince FontLoader scope-aware --font-display zincirinin
 * başına prepend eder; ÇERÇEVE FONTUNU EZMEZ — yüklenmezse zincir
 * var(--font-inter) → 'Inter' → system-ui'a düşer.
 */
import { useCallback, useEffect, useState } from "react";
import { Loader2, Star, Trash2, Upload, Type } from "lucide-react";
import {
  addGoogleFont,
  deleteFont,
  listFontsClient,
  setDefaultFont,
  uploadFont,
} from "@/lib/fonts-api";
import type { CustomFont } from "@/lib/fonts";
import type { Scope } from "@/lib/tokens";

const ACCEPT_EXTS = ".woff2,.woff,.ttf,.otf";
const FORMAT_OPTIONS = ["woff2", "woff", "ttf", "otf"] as const;
type FontFormat = (typeof FORMAT_OPTIONS)[number];

function ext(filename: string): FontFormat | null {
  const m = filename.toLowerCase().match(/\.(woff2|woff|ttf|otf)$/);
  return m ? (m[1] as FontFormat) : null;
}

export function TypographySection({
  scope,
  onChanged,
}: {
  scope: Scope;
  onChanged?: () => void;
}) {
  const [fonts, setFonts] = useState<CustomFont[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  // Google ekleme formu
  const [gFamily, setGFamily] = useState("");
  // Upload formu
  const [uFamily, setUFamily] = useState("");
  const [uFmt, setUFmt] = useState<FontFormat>("woff2");
  const [uFile, setUFile] = useState<File | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listFontsClient(scope);
      setFonts(res.fonts);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Font listesi alınamadı");
    } finally {
      setLoading(false);
    }
  }, [scope]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const handleAddGoogle = async () => {
    if (!gFamily.trim()) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await addGoogleFont({ scope, family: gFamily.trim() });
      setInfo(`Google fontu eklendi: ${gFamily.trim()}`);
      setGFamily("");
      await reload();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Google fontu eklenemedi");
    } finally {
      setBusy(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setUFile(f);
    if (f) {
      const guess = ext(f.name);
      if (guess) setUFmt(guess);
    }
  };

  const handleUpload = async () => {
    if (!uFile || !uFamily.trim()) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await uploadFont({
        scope,
        family: uFamily.trim(),
        format: uFmt,
        file: uFile,
      });
      setInfo(`Yüklendi: ${uFamily.trim()} (${uFmt})`);
      setUFile(null);
      setUFamily("");
      await reload();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload reddedildi");
    } finally {
      setBusy(false);
    }
  };

  const handleMakeDefault = async (id: number) => {
    setBusy(true);
    setError(null);
    try {
      await setDefaultFont(id);
      await reload();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Varsayılan ayarlanamadı");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: number) => {
    setBusy(true);
    setError(null);
    try {
      await deleteFont(id);
      await reload();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Silinemedi");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-3 border-t border-aq-mist/30 pt-6">
      <header className="flex items-center gap-2">
        <Type className="h-4 w-4 text-aq-quantum-2" />
        <h2 className="text-xs uppercase tracking-wider text-aq-trace">
          Tipografi · {scope}
        </h2>
      </header>

      <p className="text-[11px] text-aq-dust">
        Eklenen fontlar çerçeve fontunu EZMEZ — fallback zincirinin BAŞINA eklenir.
        Yüklenmezse tarayıcı sırayla <code>var(--font-inter)</code> → system-ui&apos;a
        düşer (regresyon-güvenli).
      </p>

      {/* --- Google Ekle --- */}
      <div className="grid grid-cols-12 items-end gap-2 rounded-md border border-aq-mist/30 bg-aq-orbital/30 p-3">
        <label className="col-span-7 text-[10px] uppercase tracking-wider text-aq-trace">
          Google Fonts aile adı
          <input
            type="text"
            value={gFamily}
            onChange={(e) => setGFamily(e.target.value)}
            placeholder="örn. Playfair Display"
            disabled={busy}
            className="mt-1 block w-full rounded bg-aq-orbital/60 px-2 py-1.5 text-sm font-mono text-aq-neutron ring-1 ring-aq-mist/40 focus:outline-none focus:ring-aq-quantum"
          />
        </label>
        <div className="col-span-5 flex gap-2">
          <button
            onClick={handleAddGoogle}
            disabled={busy || !gFamily.trim()}
            className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-aq-quantum px-3 py-1.5 text-xs font-medium text-white hover:bg-aq-quantum-2 disabled:opacity-40"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Google fontu ekle
          </button>
        </div>
      </div>

      {/* --- Upload --- */}
      <div className="grid grid-cols-12 items-end gap-2 rounded-md border border-aq-mist/30 bg-aq-orbital/30 p-3">
        <label className="col-span-5 text-[10px] uppercase tracking-wider text-aq-trace">
          Yükle: aile adı
          <input
            type="text"
            value={uFamily}
            onChange={(e) => setUFamily(e.target.value)}
            placeholder="örn. Inter Tight"
            disabled={busy}
            className="mt-1 block w-full rounded bg-aq-orbital/60 px-2 py-1.5 text-sm font-mono text-aq-neutron ring-1 ring-aq-mist/40 focus:outline-none focus:ring-aq-quantum"
          />
        </label>
        <label className="col-span-2 text-[10px] uppercase tracking-wider text-aq-trace">
          Format
          <select
            value={uFmt}
            onChange={(e) => setUFmt(e.target.value as FontFormat)}
            disabled={busy}
            className="mt-1 block w-full rounded bg-aq-orbital/60 px-2 py-1.5 text-sm font-mono text-aq-neutron ring-1 ring-aq-mist/40 focus:outline-none focus:ring-aq-quantum"
          >
            {FORMAT_OPTIONS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        <label className="col-span-3 text-[10px] uppercase tracking-wider text-aq-trace">
          Dosya
          <input
            type="file"
            accept={ACCEPT_EXTS}
            onChange={handleFileChange}
            disabled={busy}
            className="mt-1 block w-full text-[10px] text-aq-dust file:mr-2 file:rounded file:border-0 file:bg-aq-orbital/60 file:px-2 file:py-1 file:text-aq-neutron"
          />
        </label>
        <div className="col-span-2 flex">
          <button
            onClick={handleUpload}
            disabled={busy || !uFile || !uFamily.trim()}
            className="inline-flex w-full items-center justify-center gap-1 rounded-md bg-aq-quantum px-3 py-1.5 text-xs font-medium text-white hover:bg-aq-quantum-2 disabled:opacity-40"
            title="Magic-byte + boyut + format whitelist ile doğrulanır"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
            Yükle
          </button>
        </div>
      </div>

      {/* --- Mesajlar --- */}
      {error && (
        <div className="rounded-md border border-aq-fission/40 bg-aq-fission/10 px-3 py-2 text-xs text-aq-fission whitespace-pre-wrap">
          {error}
        </div>
      )}
      {info && (
        <div className="rounded-md border border-aq-fusion/40 bg-aq-fusion/10 px-3 py-2 text-xs text-aq-fusion">
          {info}
        </div>
      )}

      {/* --- Liste --- */}
      <div className="space-y-1">
        {loading && (
          <div className="flex items-center gap-2 text-xs text-aq-dust">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Yükleniyor…
          </div>
        )}
        {!loading && fonts.length === 0 && (
          <p className="rounded-md border border-aq-mist/30 bg-aq-orbital/20 px-3 py-3 text-center text-[11px] text-aq-dust">
            Bu scope&apos;a henüz font eklenmedi.
          </p>
        )}
        {fonts.map((f) => (
          <div
            key={f.id}
            className="grid grid-cols-12 items-center gap-3 rounded-md border border-aq-mist/30 px-3 py-2"
          >
            <div className="col-span-5 min-w-0">
              <div className="flex items-center gap-2">
                {f.is_default && (
                  <span className="rounded bg-aq-fusion/15 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-aq-fusion">
                    varsayılan
                  </span>
                )}
                <span
                  className="truncate font-medium text-aq-neutron"
                  style={{ fontFamily: `'${f.family}', var(--font-inter), system-ui, sans-serif` }}
                  title={`${f.source} · ${f.family}`}
                >
                  {f.family}
                </span>
              </div>
              <div className="text-[10px] text-aq-dust">
                {f.source}
                {f.format ? ` · ${f.format}` : ""}
                {f.weight ? ` · ${f.weight}` : ""}
              </div>
            </div>
            <div
              className="col-span-4 truncate text-sm"
              style={{ fontFamily: `'${f.family}', var(--font-inter), system-ui, sans-serif` }}
            >
              Aa Bb Cc 0123 — Alpha Quantum
            </div>
            <div className="col-span-3 flex items-center justify-end gap-1">
              <button
                onClick={() => handleMakeDefault(f.id)}
                disabled={busy || f.is_default}
                title="Bu scope için varsayılan yap"
                className="rounded p-1.5 text-aq-solar hover:bg-aq-solar/10 disabled:opacity-30"
              >
                <Star className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => handleDelete(f.id)}
                disabled={busy}
                title="Sil"
                className="rounded p-1.5 text-aq-fission hover:bg-aq-fission/10 disabled:opacity-30"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
