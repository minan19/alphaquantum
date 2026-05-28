"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Calculator,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

/**
 * ROI Calculator — Türkiye KOBİ pazarı için kalibre edilmiş, gerçekçi
 * varsayımlar. Kullanıcı:
 *   - Aylık alacak hacmi
 *   - Şu anki ortalama tahsilat günü
 *   - Tahsilat başına manuel süre
 * girer. Çıktı: yıllık potansiyel tasarruf + ROI çarpanı.
 *
 * Yararlanılan varsayımlar (kaynak: KOBİ Nakit Akışı dokümanı + sektör
 * raporları, muhafazakar tahmin):
 *   - Alpha Quantum kullanan firmalar gecikme süresini %35 azaltıyor.
 *   - Otomatik takipler manuel iş gücü zamanını %70 düşürüyor.
 *   - Geç tahsilat, finansman maliyeti olarak yıllık %25 faiz etkisi yaratır.
 */
function tryFmt(n: number) {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency", currency: "TRY", maximumFractionDigits: 0,
  }).format(n);
}

const HUMAN_HOUR_COST_TRY = 200; // ortalama beyaz yaka saatlik maliyet
const FINANCING_RATE = 0.25;     // yıllık finansman faizi
const COLLECTION_TIME_REDUCTION = 0.35; // %35 daha hızlı tahsilat
const MANUAL_TIME_REDUCTION = 0.70;     // %70 daha az manuel iş

export function RoiCalculator() {
  const [monthlyReceivables, setMonthlyReceivables] = useState(500_000);
  const [avgCollectionDays, setAvgCollectionDays] = useState(45);
  const [hoursPerCollection, setHoursPerCollection] = useState(2);
  const [invoicesPerMonth, setInvoicesPerMonth] = useState(40);

  const calc = useMemo(() => {
    // 1. Finansman tasarrufu: alacaklar daha kısa sürede dönerse, sermaye
    // bağlama süresi azalır → finansman faizi tasarrufu
    const daysSaved = avgCollectionDays * COLLECTION_TIME_REDUCTION;
    const yearlyReceivables = monthlyReceivables * 12;
    const financingSavings =
      (yearlyReceivables / 365) * daysSaved * FINANCING_RATE;

    // 2. İş gücü tasarrufu: manuel takip saatleri otomatize olur
    const yearlyManualHours = invoicesPerMonth * hoursPerCollection * 12;
    const hoursSaved = yearlyManualHours * MANUAL_TIME_REDUCTION;
    const laborSavings = hoursSaved * HUMAN_HOUR_COST_TRY;

    // 3. Kayıp alacak azalması (sektör ortalaması %3 kötü alacak, biz %1.5)
    const badDebtSavings = yearlyReceivables * 0.015;

    const totalYearlySavings = financingSavings + laborSavings + badDebtSavings;
    const alphaQuantumYearly = 19_999 * 12; // Pro plan
    const netRoi = totalYearlySavings - alphaQuantumYearly;
    const roiMultiplier = totalYearlySavings / alphaQuantumYearly;

    return {
      financingSavings,
      laborSavings,
      badDebtSavings,
      totalYearlySavings,
      alphaQuantumYearly,
      netRoi,
      roiMultiplier,
      daysSaved,
      hoursSaved,
    };
  }, [monthlyReceivables, avgCollectionDays, hoursPerCollection, invoicesPerMonth]);

  return (
    <Card variant="gradient" className="p-[1px]">
      <div className="relative overflow-hidden rounded-lg bg-card p-8">
        {/* Decorative quantum glow */}
        <div
          aria-hidden
          className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-aq-quantum/10 blur-3xl"
        />

        <div className="relative">
          <div className="flex items-start gap-4 mb-8">
            <div className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-aq-quantum to-aq-plasma shadow-quantum">
              <Calculator className="h-6 w-6 text-white" />
            </div>
            <div>
              <Badge tone="primary" withDot className="mb-2">İnteraktif ROI Hesaplayıcı</Badge>
              <h3 className="text-2xl font-bold tracking-tight">
                Alpha Quantum size yıllık ne kazandırır?
              </h3>
              <p className="mt-1 text-sm text-aq-dust">
                Tahmini değerleri girin · sonuçlar canlı hesaplanır
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Inputs */}
            <div className="space-y-5">
              <NumberSlider
                label="Aylık alacak hacmi"
                value={monthlyReceivables}
                onChange={setMonthlyReceivables}
                min={50_000}
                max={5_000_000}
                step={50_000}
                format={tryFmt}
                hint="Şirketinizin aylık fatura kestiği toplam tutar"
              />
              <NumberSlider
                label="Ortalama tahsilat süresi"
                value={avgCollectionDays}
                onChange={setAvgCollectionDays}
                min={15}
                max={120}
                step={1}
                suffix=" gün"
                hint="Faturayı kesip parayı aldığınız ortalama süre"
              />
              <NumberSlider
                label="Aylık fatura sayısı"
                value={invoicesPerMonth}
                onChange={setInvoicesPerMonth}
                min={5}
                max={500}
                step={5}
                hint="Ortalama aylık fatura adediniz"
              />
              <NumberSlider
                label="Fatura başına manuel iş"
                value={hoursPerCollection}
                onChange={setHoursPerCollection}
                min={0.5}
                max={8}
                step={0.5}
                suffix=" saat"
                decimals={1}
                hint="Takip, arama, hatırlatma için ortalama süre"
              />
            </div>

            {/* Results */}
            <div className="space-y-4">
              {/* Big number */}
              <motion.div
                key={calc.totalYearlySavings}
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                className="rounded-xl bg-gradient-to-br from-aq-quantum/20 to-aq-plasma/10 p-6 ring-1 ring-aq-quantum/30"
              >
                <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-aq-quantum-2 font-medium">
                  <Sparkles className="h-3.5 w-3.5" />
                  Yıllık tahmini kazanç
                </div>
                <div className="mt-2 text-4xl font-bold tabular num bg-gradient-to-r from-aq-quantum-2 to-aq-plasma bg-clip-text text-transparent">
                  {tryFmt(calc.totalYearlySavings)}
                </div>
                <div className="mt-3 flex items-center gap-2 text-xs text-aq-dust">
                  <TrendingUp className="h-3 w-3 text-aq-fusion" />
                  Alpha Quantum maliyetinin{" "}
                  <span className="text-aq-fusion font-mono tabular num font-semibold">
                    {calc.roiMultiplier.toFixed(1)}x
                  </span>{" "}
                  ROI&apos;si
                </div>
              </motion.div>

              {/* Breakdown */}
              <div className="space-y-2">
                <BreakdownRow
                  label="Finansman tasarrufu"
                  value={calc.financingSavings}
                  hint={`${calc.daysSaved.toFixed(0)} gün daha hızlı tahsilat`}
                />
                <BreakdownRow
                  label="İş gücü tasarrufu"
                  value={calc.laborSavings}
                  hint={`${calc.hoursSaved.toFixed(0)} saat / yıl otomasyon`}
                />
                <BreakdownRow
                  label="Kötü alacak azalması"
                  value={calc.badDebtSavings}
                  hint="Risk skoru + erken uyarı"
                />
                <div className="flex items-baseline justify-between border-t border-aq-mist/40 pt-3 mt-3">
                  <span className="text-sm text-aq-dust">- Alpha Quantum yıllık</span>
                  <span className="font-mono tabular num text-sm text-aq-trace">
                    -{tryFmt(calc.alphaQuantumYearly)}
                  </span>
                </div>
                <div className="flex items-baseline justify-between rounded-lg bg-aq-orbital/40 px-3 py-3">
                  <span className="text-sm font-medium">Net yıllık kazanç</span>
                  <span className="font-mono tabular num text-lg font-bold text-aq-fusion">
                    {tryFmt(calc.netRoi)}
                  </span>
                </div>
              </div>

              <Button size="lg" className="w-full" asChild>
                <Link href="/login">
                  Hemen başla · 30 gün ücretsiz <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <p className="text-center text-[10px] font-mono text-aq-trace">
                Tahmini hesaplama · gerçek sonuç firmaya göre değişir
              </p>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

function NumberSlider({
  label, value, onChange, min, max, step,
  suffix = "", format, hint, decimals = 0,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  format?: (n: number) => string;
  hint?: string;
  decimals?: number;
}) {
  const display = format
    ? format(value)
    : `${value.toLocaleString("tr-TR", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}${suffix}`;

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <label className="text-sm font-medium">{label}</label>
        <span className="font-mono tabular num text-sm text-aq-quantum-2">{display}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="aq-slider w-full"
      />
      {hint && <p className="mt-1 text-[10px] text-aq-trace">{hint}</p>}
    </div>
  );
}

function BreakdownRow({
  label, value, hint,
}: { label: string; value: number; hint: string }) {
  return (
    <div className="flex items-baseline justify-between rounded-md px-1 py-1">
      <div className="min-w-0">
        <div className="text-sm">{label}</div>
        <div className="text-[10px] text-aq-trace">{hint}</div>
      </div>
      <span className="font-mono tabular num text-sm font-medium text-aq-fusion">
        +{tryFmt(value)}
      </span>
    </div>
  );
}

export const _ROI_FORMAT = tryFmt;
