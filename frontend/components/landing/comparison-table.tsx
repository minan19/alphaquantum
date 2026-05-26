"use client";

import { motion } from "framer-motion";
import { Check, Minus, X } from "lucide-react";
import { Logomark } from "@/components/brand/logomark";
import { cn } from "@/lib/cn";

type Cell = true | false | "partial" | string;

interface Row {
  feature: string;
  excel: Cell;
  paraşüt: Cell;
  alphaQuantum: Cell;
  hint?: string;
}

const ROWS: Row[] = [
  { feature: "Çoklu şirket / holding yönetimi",        excel: false, paraşüt: false, alphaQuantum: true },
  { feature: "Otomatik vade hatırlatma (T-3/T+7)",      excel: false, paraşüt: "partial", alphaQuantum: true,
    hint: "Alpha Quantum: WhatsApp/SMS/E-posta otomatik dispatch" },
  { feature: "Müşteri ödeme risk skoru",                excel: false, paraşüt: false, alphaQuantum: true },
  { feature: "30/60/90 gün nakit projeksiyonu",        excel: "partial", paraşüt: "partial", alphaQuantum: true },
  { feature: "Alacak yaşlandırma (aging) analizi",     excel: "partial", paraşüt: true, alphaQuantum: true },
  { feature: "FX exposure raporu (USD/EUR/GBP)",       excel: false, paraşüt: false, alphaQuantum: true },
  { feature: "Senet / Çek / Bono takibi",              excel: "partial", paraşüt: true, alphaQuantum: true },
  { feature: "KVKK uyumlu consent yönetimi",           excel: false, paraşüt: "partial", alphaQuantum: true },
  { feature: "Konsolide finansal raporlama",           excel: false, paraşüt: false, alphaQuantum: true },
  { feature: "AI tahsilat koçu (LLM)",                 excel: false, paraşüt: false, alphaQuantum: true },
  { feature: "Multi-currency invoicing",                excel: "partial", paraşüt: true, alphaQuantum: true },
  { feature: "İmzalı PDF/Excel export",                 excel: false, paraşüt: true, alphaQuantum: true },
  { feature: "OAuth2 / SSO desteği",                    excel: false, paraşüt: false, alphaQuantum: "Enterprise" },
  { feature: "Manuel iş yükü",                          excel: "Çok yüksek", paraşüt: "Orta", alphaQuantum: "Düşük" },
];

export function ComparisonTable() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-aq-mist/40">
            <th className="px-4 py-4 text-left font-medium text-aq-trace uppercase text-[10px] tracking-wider">
              Özellik
            </th>
            <th className="px-4 py-4 text-center">
              <div className="flex flex-col items-center gap-1">
                <span className="text-sm font-semibold text-aq-dust">Excel</span>
                <span className="text-[10px] font-mono text-aq-trace">Manuel</span>
              </div>
            </th>
            <th className="px-4 py-4 text-center">
              <div className="flex flex-col items-center gap-1">
                <span className="text-sm font-semibold text-aq-dust">Paraşüt / Logo</span>
                <span className="text-[10px] font-mono text-aq-trace">Klasik muhasebe</span>
              </div>
            </th>
            <th className="px-4 py-4 text-center bg-gradient-to-b from-aq-quantum/10 to-transparent rounded-t-lg">
              <div className="flex flex-col items-center gap-1.5">
                <div className="flex items-center gap-1.5">
                  <Logomark size={16} />
                  <span className="text-sm font-bold bg-gradient-to-r from-aq-quantum-2 to-aq-plasma bg-clip-text text-transparent">
                    Alpha Quantum
                  </span>
                </div>
                <span className="text-[10px] font-mono text-aq-quantum-2">CorpOS + FinOS</span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row, i) => (
            <motion.tr
              key={row.feature}
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true, amount: 0.1 }}
              transition={{ duration: 0.4, delay: i * 0.03 }}
              className="border-b border-aq-mist/30 group hover:bg-aq-quantum/5 transition-colors"
            >
              <td className="px-4 py-3.5 text-aq-dust group-hover:text-foreground transition-colors">
                <div>
                  <div>{row.feature}</div>
                  {row.hint && (
                    <div className="text-[10px] text-aq-trace mt-0.5">{row.hint}</div>
                  )}
                </div>
              </td>
              <td className="px-4 py-3.5 text-center">
                <CellIcon value={row.excel} />
              </td>
              <td className="px-4 py-3.5 text-center">
                <CellIcon value={row.paraşüt} />
              </td>
              <td className="px-4 py-3.5 text-center bg-aq-quantum/5">
                <CellIcon value={row.alphaQuantum} highlight />
              </td>
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CellIcon({ value, highlight }: { value: Cell; highlight?: boolean }) {
  if (value === true) {
    return (
      <div className="inline-flex items-center justify-center">
        <div className={cn(
          "grid h-7 w-7 place-items-center rounded-full",
          highlight
            ? "bg-gradient-to-br from-aq-fusion to-aq-fusion/70 shadow-[0_0_12px_rgba(34,197,94,0.4)]"
            : "bg-aq-fusion/15 ring-1 ring-aq-fusion/30",
        )}>
          <Check className={cn("h-3.5 w-3.5", highlight ? "text-white" : "text-aq-fusion")} />
        </div>
      </div>
    );
  }
  if (value === false) {
    return (
      <div className="inline-flex items-center justify-center">
        <div className="grid h-7 w-7 place-items-center rounded-full bg-aq-fission/10 ring-1 ring-aq-fission/30">
          <X className="h-3.5 w-3.5 text-aq-fission/80" />
        </div>
      </div>
    );
  }
  if (value === "partial") {
    return (
      <div className="inline-flex items-center justify-center">
        <div className="grid h-7 w-7 place-items-center rounded-full bg-aq-solar/10 ring-1 ring-aq-solar/30">
          <Minus className="h-3.5 w-3.5 text-aq-solar" />
        </div>
      </div>
    );
  }
  // String label
  return (
    <span className={cn(
      "inline-block rounded-full px-2.5 py-0.5 text-xs font-medium",
      highlight
        ? "bg-aq-quantum/20 text-aq-quantum-2 ring-1 ring-aq-quantum/30"
        : "bg-aq-mist/40 text-aq-dust",
    )}>
      {value}
    </span>
  );
}
