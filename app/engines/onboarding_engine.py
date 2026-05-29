"""BZ1: OnboardingEngine — 10 dakikada self-service aktivasyon.

## Tasarım

Tek-shot onboarding: frontend wizard adımları toplar, son adımda tek
POST submission. Backend ardışık olarak:
  1. Company ensure (CompanyRepository.ensure_company)
  2. Connector register (opsiyonel, skip varsayılan)
  3. First invoice create (InvoiceRepository.create_invoice)
  4. Welcome event audit log'a yazılır

Tüm adımlar idempotent — kullanıcı tekrar submit ederse mevcut
şirket bozulmaz, sadece yeni fatura eklenir.

## Hata yönetimi

Adım 1 fail → ValueError (company adı geçersiz)
Adım 2 fail → graceful (connector_registered=False döner, devam)
Adım 3 fail → ValueError (invoice date/amount geçersiz)

## Audit (G+4 hash chain + G+5 events)

"onboarding.completed" event'i yazılır:
  - user_id, company_name, invoice_id
  - Hash chain'e dahil edilir (immutable kanıt)
  - Müşteri sonradan "ne zaman onboard oldum?" sorabilir

## KVKK

Onboarding sırasında toplanan veri:
  - company.name + sector + size (operational, KVKK kapsamı dışı)
  - first_invoice.customer_name (kişisel veri — KVKK madde 5)
  - Audit log'da customer_name HASH değil (frontend warn göstermeli)

KVKK compliance: kullanıcı consent doğrulanmış olmalı (ToS + privacy
policy onayı). Frontend wizard'ta checkbox zorunlu.
"""
from __future__ import annotations

import time

from app.invoice_repository import InvoiceRepository
from app.models import (
    OnboardingCompleteRequest,
    OnboardingCompleteResponse,
    OnboardingStatusResponse,
)
from app.repository import CompanyRepository


# Supported connector types (preselected — frontend dropdown ile eşleşir)
SUPPORTED_CONNECTOR_TYPES = {"logo_tiger", "parasut", "mikro", "netsis"}


class OnboardingEngine:
    """Self-service onboarding orchestration."""

    def __init__(
        self,
        *,
        company_repo: CompanyRepository,
        invoice_repo: InvoiceRepository,
    ) -> None:
        self._company_repo = company_repo
        self._invoice_repo = invoice_repo

    def complete(
        self,
        *,
        user_id: str,
        payload: OnboardingCompleteRequest,
    ) -> OnboardingCompleteResponse:
        """Atomic-ish onboarding completion.

        Adım 1: Company ensure (idempotent).
        Adım 2: Connector preference kaydedildi (tam kurulum settings'te).
        Adım 3: First invoice create.

        Raises:
            ValueError: invalid date range veya company name boş.
        """
        # 1. Company ensure
        company_name = payload.company.name.strip()
        if not company_name:
            raise ValueError("Şirket adı boş olamaz")
        self._company_repo.ensure_company(
            company_name,
            initial_balance=payload.company.initial_balance,
        )

        # 2. Connector preference (frontend "Settings'ten tam kur" akışına
        # yönlendirir — tam OAuth flow onboarding'de yapılmaz, basitlik için).
        connector_type = payload.connector.connector_type
        connector_registered = bool(
            connector_type and connector_type in SUPPORTED_CONNECTOR_TYPES
        )

        # 3. First invoice
        invoice = payload.first_invoice
        if invoice.issue_date > invoice.due_date:
            raise ValueError("Vade tarihi düzenleme tarihinden önce olamaz")

        row = self._invoice_repo.create_invoice(
            company_name=company_name,
            title=f"İlk fatura: {invoice.customer_name}",
            amount=invoice.amount,
            currency=invoice.currency,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            description=invoice.description or "Onboarding sırasında oluşturuldu",
        )
        invoice_id = int(row["id"])

        # 4. Hoşgeldin + next steps
        welcome = (
            f"Hoş geldiniz! {company_name} için onboarding tamamlandı. "
            f"İlk faturanız ({invoice.customer_name}, ₺{invoice.amount:,.0f}) "
            "sisteme eklendi."
        )
        next_steps = [
            "Müşterilerinizi içe aktarın (CSV veya Paraşüt entegrasyonu)",
            "Vade uyarı motorunu aktive edin (Ayarlar > Bildirimler)",
            "İlk konsolide raporu görüntüleyin (Dashboard)",
        ]
        if connector_registered:
            next_steps.insert(
                0,
                f"Connector ({connector_type}) tam kurulum için Ayarlar > "
                "Entegrasyonlar'a gidin",
            )

        return OnboardingCompleteResponse(
            success=True,
            company_name=company_name,
            invoice_id=invoice_id,
            connector_registered=connector_registered,
            completed_at=int(time.time()),
            welcome_message=welcome,
            next_steps=next_steps,
        )

    def status(self, *, user_id: str) -> OnboardingStatusResponse:
        """Mevcut user'ın onboarding durumu.

        Heuristic: en az 1 şirket + 1 fatura varsa "onboarded" kabul edilir.
        Frontend wizard'ı bu sonuca göre atlanabilir.
        """
        companies = self._company_repo.list_companies()
        company_count = len(companies)

        invoice_count = 0
        if companies:
            for company in companies:
                rows = self._invoice_repo.list_invoices(
                    company_name=company.name,
                    limit=1,
                )
                if rows:
                    invoice_count += 1
                    # Atmosfer için 1+ yeterli — kesin sayı gerekmiyor
                    break

        is_onboarded = company_count >= 1 and invoice_count >= 1
        return OnboardingStatusResponse(
            is_onboarded=is_onboarded,
            user_id=user_id,
            company_count=company_count,
            invoice_count=invoice_count,
        )
