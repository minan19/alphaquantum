/**
 * G1.6: Storytelling seed data — backend API contract'ı ile birebir uyumlu.
 *
 * "Atlas Holding" karma sektör senaryo (İnşaat + Lojistik + Gıda + Tekstil).
 * Tüm değerler gerçek backend API'lerin (G1.2 + G1.3 + G1.4 + G1.5) response
 * shape'lerine uygun — yani storytelling mockup'ları artık "vapor demo" değil,
 * gerçek bir holding'in günlük operasyonunu yansıtan canlı veri yapısı.
 *
 * Backend canlıysa frontend bu seed yerine gerçek API'yi çağırır
 * (corpos-api.ts helper'ları). Pricing sayfası public olduğu için bu seed
 * fallback olarak da kullanılır.
 *
 * Tüm rakamlar tutarlı: konsolide gross > consolidated, eliminasyon balanced,
 * FX net pozisyon sensitivity scenarios doğru, intercompany transfer 4-eyes
 * workflow state machine'i temsil ediyor.
 */
import type {
  ConsolidatedPLResponse,
  ExecSummaryResponse,
  FinanceOverviewResponse,
  GroupFXPositionResponse,
  IntercompanyTransferListResponse,
} from "@/lib/corpos-api";

// ── Sahne 1: Ledger-derived overview (sabah bakiyesi) ─────────────────────

export const ATLAS_HOLDING_OVERVIEW_SEED: FinanceOverviewResponse = {
  total_balance: 847_230,
  average_balance: 211_807.5,
  negative_balance_companies: 0,
  highest_balance_company: "Atlas İnşaat A.Ş.",
  lowest_balance_company: "Atlas Tekstil A.Ş.",
  health_status: "HEALTHY",
};

// ── Sahne 1 (FX): Group FX position (sabah FX nabız) ──────────────────────

export const ATLAS_HOLDING_FX_SEED: GroupFXPositionResponse = {
  holding_id: 1,
  holding_name: "Atlas Holding",
  as_of_date: "2026-05-29",
  exposures: [
    {
      currency: "EUR",
      fx_rate_to_try: 35.0,
      receivable_open: 180_000,
      receivable_overdue: 12_000,
      intercompany_inflow: 0,
      intercompany_outflow: 0,
      net_position_fx: 180_000,
      net_position_try: 6_300_000,
      position_type: "long",
    },
    {
      currency: "USD",
      fx_rate_to_try: 32.5,
      receivable_open: 95_000,
      receivable_overdue: 8_500,
      intercompany_inflow: 25_000,
      intercompany_outflow: 25_000,
      net_position_fx: 95_000,
      net_position_try: 3_087_500,
      position_type: "long",
    },
    {
      currency: "GBP",
      fx_rate_to_try: 41.0,
      receivable_open: 15_000,
      receivable_overdue: 0,
      intercompany_inflow: 0,
      intercompany_outflow: 0,
      net_position_fx: 15_000,
      net_position_try: 615_000,
      position_type: "long",
    },
  ],
  total_long_try: 10_002_500,
  total_short_try: 0,
  net_exposure_try: 10_002_500,
  sensitivity_scenarios: [
    {
      scenario_name: "TL %5 değer kaybı",
      devaluation_pct: 0.05,
      total_impact_try: 500_125,
    },
    {
      scenario_name: "TL %10 değer kaybı",
      devaluation_pct: 0.1,
      total_impact_try: 1_000_250,
    },
    {
      scenario_name: "TL %20 değer kaybı (kriz senaryosu)",
      devaluation_pct: 0.2,
      total_impact_try: 2_000_500,
    },
  ],
  risk_level: "concentrated",
  recommendations: [
    "🟠 Yüksek konsantrasyon. Doğal hedge fırsatlarını gözden geçirin.",
    "• EUR long pozisyonu ₺6,300,000 — TL değer kazanırsa azalır.",
    "• USD long pozisyonu ₺3,087,500 — Forward satım koruyucu olabilir.",
  ],
};

// ── Sahne 2: Consolidated P&L (yönetim toplantısı) ───────────────────────

export const ATLAS_HOLDING_CONSOLIDATED_PL_SEED: ConsolidatedPLResponse = {
  holding_id: 1,
  holding_name: "Atlas Holding",
  period_start: "2026-01-01",
  period_end: "2026-03-31",
  lines: [
    {
      company: "Atlas İnşaat A.Ş.",
      gross_income: 1_400_000,
      intercompany_income: 0,
      external_income: 1_400_000,
      gross_expense: 480_000,
      intercompany_expense: 120_000,
      external_expense: 360_000,
      net_total: 920_000,
      net_external: 1_040_000,
    },
    {
      company: "Atlas Lojistik A.Ş.",
      gross_income: 720_000,
      intercompany_income: 150_000,
      external_income: 570_000,
      gross_expense: 260_000,
      intercompany_expense: 0,
      external_expense: 260_000,
      net_total: 460_000,
      net_external: 310_000,
    },
    {
      company: "Atlas Gıda A.Ş.",
      gross_income: 480_000,
      intercompany_income: 0,
      external_income: 480_000,
      gross_expense: 195_000,
      intercompany_expense: 30_000,
      external_expense: 165_000,
      net_total: 285_000,
      net_external: 315_000,
    },
    {
      company: "Atlas Tekstil A.Ş.",
      gross_income: 200_000,
      intercompany_income: 0,
      external_income: 200_000,
      gross_expense: 85_000,
      intercompany_expense: 0,
      external_expense: 85_000,
      net_total: 115_000,
      net_external: 115_000,
    },
  ],
  gross_total_income: 2_800_000,
  gross_total_expense: 1_020_000,
  gross_net: 1_780_000,
  consolidated_income: 2_650_000,
  consolidated_expense: 870_000,
  consolidated_net: 1_780_000,
  elimination: {
    total_intercompany_income: 150_000,
    total_intercompany_expense: 150_000,
    elimination_amount: 300_000,
    is_balanced: true,
  },
  health_status: "strong",
};

// ── Sahne 4: Intercompany transfer pending queue (cross-company) ─────────

export const ATLAS_HOLDING_PENDING_TRANSFERS_SEED: IntercompanyTransferListResponse = {
  total: 2,
  transfers: [
    {
      id: 142,
      holding_id: 1,
      from_company: "Atlas Lojistik A.Ş.",
      to_company: "Atlas Gıda A.Ş.",
      amount: 100_000,
      currency: "TRY",
      target_amount: null,
      fx_rate: null,
      description: "Q2 kaynak desteği — depolama maliyeti",
      requested_by: "cfo@atlas.tr",
      requested_at: 1716969600,
      approval_status: "pending",
      approved_by: null,
      approved_at: null,
      reject_reason: null,
      completed_at: null,
      ledger_entry_from_id: null,
      ledger_entry_to_id: null,
    },
    {
      id: 143,
      holding_id: 1,
      from_company: "Atlas İnşaat A.Ş.",
      to_company: "Atlas Tekstil A.Ş.",
      amount: 75_000,
      currency: "TRY",
      target_amount: null,
      fx_rate: null,
      description: "Şantiye tekstil iş elbisesi sipariş ön ödeme",
      requested_by: "ops@atlas.tr",
      requested_at: 1716955200,
      approval_status: "pending",
      approved_by: null,
      approved_at: null,
      reject_reason: null,
      completed_at: null,
      ledger_entry_from_id: null,
      ledger_entry_to_id: null,
    },
  ],
};

// ── Sahne 5: Executive Summary (G+1 AI Layer) ────────────────────────────

export const ATLAS_HOLDING_EXEC_SUMMARY_SEED: ExecSummaryResponse = {
  holding_id: 1,
  holding_name: "Atlas Holding",
  period_start: "2026-01-01",
  period_end: "2026-03-31",
  generated_at: "2026-03-31",
  narrative:
    "Atlas Holding için 2026-01-01 - 2026-03-31 döneminde konsolide net sonuç " +
    "₺1.780.000 (güçlü), toplam brüt gelir ₺2.800.000. FX net pozisyonu " +
    "₺10.002.500 ile konsantre seviyede.\n\n" +
    "Intercompany eliminasyonu dengeli. 2 adet bekleyen intercompany transfer " +
    "4-eyes onay sırasında.\n\n" +
    "Öneriler:\n" +
    "• FX konsantrasyonu yüksek — hedging stratejisi (forward/swap) değerlendirilmeli.\n" +
    "• Mevcut göstergeler sağlıklı — rutin haftalık review yeterli.",
  highlights: [
    "🟢 Konsolide net: ₺1.780.000 (strong)",
    "🟠 FX net pozisyon: ₺10.002.500 (concentrated)",
    "⏳ 2 adet intercompany transfer 4-eyes onay sırasında",
  ],
  health_status: "strong",
  fx_risk_level: "concentrated",
  consolidated_net_try: 1_780_000,
  fx_net_exposure_try: 10_002_500,
  pending_transfers_count: 2,
};


// ── Helper: TR locale formatlar ──────────────────────────────────────────

/**
 * Türk Lirası format (₺ + tabular nums + binlik ayraç).
 * Compactsa M/B (milyon/binyon) suffix.
 */
export function formatTRY(amount: number, compact = false): string {
  if (compact) {
    if (Math.abs(amount) >= 1_000_000) {
      return `₺${(amount / 1_000_000).toLocaleString("tr-TR", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })}M`;
    }
    if (Math.abs(amount) >= 1_000) {
      return `₺${Math.round(amount / 1_000).toLocaleString("tr-TR")}K`;
    }
  }
  return `₺${amount.toLocaleString("tr-TR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

/**
 * FX format (kod + tutar). Compactsa M/K suffix.
 */
export function formatFX(
  amount: number,
  currency: string,
  compact = false,
): string {
  if (compact) {
    if (Math.abs(amount) >= 1_000_000) {
      return `${currency} ${(amount / 1_000_000).toLocaleString("tr-TR", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })}M`;
    }
    if (Math.abs(amount) >= 1_000) {
      return `${currency} ${Math.round(amount / 1_000).toLocaleString("tr-TR")}K`;
    }
  }
  return `${currency} ${amount.toLocaleString("tr-TR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}
