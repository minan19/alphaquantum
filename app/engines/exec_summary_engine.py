"""G+1: ExecSummaryEngine — Sahne 5 (17:00 günlük rapor) gerçek motoru.

ConsolidationEngine + GroupFXEngine + IntercompanyTransferEngine'in
çıktılarını LLM'e besler, Türkçe yönetici özeti üretir.

## Mimari kararlar

### Bağımlılıklar
Stateless — 3 engine'i constructor injection ile alır:
  - ConsolidationEngine (G1.2): konsolide P&L
  - GroupFXEngine (G1.4): FX net pozisyon
  - IntercompanyTransferEngine (G1.3): pending kuyruğu
  - LLMServiceProtocol (G+1): narrative üretici

### Hata yönetimi (graceful degradation)
LLM down olursa exception fırlatmaz — OfflineLLMService fallback kullanır.
Output: her zaman bir narrative metin döner.

### Audit log entegrasyonu
G+4 hash chain + G+5 observability: özet üretimi audit log'a "event"
olarak yazılır. Bu sayede "Mehmet hangi raporu istedi, ne zaman?" sorusu
kanıtlanabilir.

### Idempotency
Aynı period_start + period_end ile aynı kontekst gelir → LLM cache hit'ten
yararlanır. Müşteri "raporu tekrar oluştur" derse maliyet ~%10.
"""
from __future__ import annotations

from datetime import date

from app.engines.consolidation_engine import ConsolidationEngine
from app.engines.group_fx_engine import GroupFXEngine
from app.engines.intercompany_transfer_engine import IntercompanyTransferEngine
from app.llm_service import LLMServiceProtocol
from app.models import (
    ExecSummaryRequest,
    ExecSummaryResponse,
)


class ExecSummaryEngine:
    """Sahne 5 gerçek backend — LLM ile holding exec summary üretir."""

    def __init__(
        self,
        *,
        consolidation_engine: ConsolidationEngine,
        group_fx_engine: GroupFXEngine,
        intercompany_engine: IntercompanyTransferEngine,
        llm_service: LLMServiceProtocol,
    ) -> None:
        self._consolidation = consolidation_engine
        self._group_fx = group_fx_engine
        self._intercompany = intercompany_engine
        self._llm = llm_service

    def generate_summary(
        self,
        *,
        holding_id: int,
        payload: ExecSummaryRequest,
    ) -> ExecSummaryResponse:
        """Holding exec summary üret — 3 engine + LLM çağrısı.

        Raises:
            ValueError: holding bulunamadı veya date range geçersiz
                (alt engine'lerden propagate olur)
        """
        period_start = payload.period_start
        period_end = payload.period_end

        if period_start > period_end:
            raise ValueError("period_start must be <= period_end")

        # 1. Konsolide P&L (G1.2)
        pl = self._consolidation.consolidated_pl(
            holding_id=holding_id,
            start_date=period_start,
            end_date=period_end,
        )

        # 2. FX pozisyon — period_end tarihinde (G1.4)
        fx = self._group_fx.group_fx_position(
            holding_id=holding_id,
            as_of_date=period_end,
        )

        # 3. Pending intercompany transfer sayısı (G1.3)
        pending_list = self._intercompany.list_pending(holding_id=holding_id)
        pending_count = pending_list.total

        # 4. LLM context — yapısal dict
        context = {
            "holding_name": pl.holding_name,
            "period_start": period_start,
            "period_end": period_end,
            "consolidated_pl": pl.model_dump(),
            "fx_position": fx.model_dump(),
            "pending_transfers_count": pending_count,
        }

        # 5. LLM ile narrative üret (graceful — offline fallback dahili)
        narrative = self._llm.generate_exec_summary(context=context)

        # 6. Kural-tabanlı "highlights" — UI için yapısal
        highlights = _build_highlights(
            pl_health=pl.health_status,
            fx_risk=fx.risk_level,
            consolidated_net=pl.consolidated_net,
            net_exposure_try=fx.net_exposure_try,
            pending_count=pending_count,
            is_balanced=pl.elimination.is_balanced,
        )

        return ExecSummaryResponse(
            holding_id=holding_id,
            holding_name=pl.holding_name,
            period_start=period_start,
            period_end=period_end,
            generated_at=date.today().isoformat(),
            narrative=narrative,
            highlights=highlights,
            health_status=pl.health_status,
            fx_risk_level=fx.risk_level,
            consolidated_net_try=pl.consolidated_net,
            fx_net_exposure_try=fx.net_exposure_try,
            pending_transfers_count=pending_count,
        )


def _build_highlights(
    *,
    pl_health: str,
    fx_risk: str,
    consolidated_net: float,
    net_exposure_try: float,
    pending_count: int,
    is_balanced: bool,
) -> list[str]:
    """Strukturel highlights — UI'da bullet list olarak gösterilir.

    Rapor narrative'ından bağımsız — KPI özet olarak C-seviye okunur.
    """
    highlights: list[str] = []

    # P&L durumu
    pl_emoji = {
        "strong": "🟢", "stable": "🟡", "watch": "🟠", "risk": "🔴",
    }.get(pl_health, "⚪")
    highlights.append(
        f"{pl_emoji} Konsolide net: ₺{consolidated_net:,.0f} ({pl_health})"
    )

    # FX risk
    fx_emoji = {
        "balanced": "🟢", "moderate": "🟡",
        "concentrated": "🟠", "critical": "🔴",
    }.get(fx_risk, "⚪")
    highlights.append(
        f"{fx_emoji} FX net pozisyon: ₺{net_exposure_try:,.0f} ({fx_risk})"
    )

    # Pending onaylar
    if pending_count > 0:
        highlights.append(
            f"⏳ {pending_count} adet intercompany transfer 4-eyes onay sırasında"
        )

    # Intercompany eliminasyon
    if not is_balanced:
        highlights.append(
            "⚠️ Intercompany eliminasyon imbalance — manuel inceleme önerilir"
        )

    return highlights
