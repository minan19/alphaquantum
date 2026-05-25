# Alpha Quantum – Claude Proje Yönetim Dosyası

**Branch:** `23martclaude`
**Yönetim Başlangıcı:** 24 Mart 2026
**Kurallar:** Main branch'e doğrudan commit yapılmaz. Tüm değişiklikler `23martclaude` üzerinden geliştirilir, PR ile main'e alınır.

---

## Mevcut Durum (24 Mart 2026)

### Faz Özeti
| Faz | Durum |
|---|---|
| Faz 1 – Backend + Auth + Security Gate | ✅ Tamamlandı |
| Faz 2 – Sprint 2.1 (Governance + Ölçüm) | ✅ Tamamlandı |
| Faz 2 – Sprint 2.2 (Altyapı Dayanıklılık + API Operasyon) | ✅ Tamamlandı |
| Faz 2 – Sprint 2.3 (Ürün Paketleme + UX İyileştirme) | 🔄 Aktif |
| Faz 3 – Gelişmiş Dijital Platform | 📋 Planlandı |

### Sprint 2.3 Aktif Görevler
| Story ID | Başlık | Durum |
|---|---|---|
| S-231 | Rol bazlı dashboard akışları | Bekliyor |
| S-232 | Kritik kart kullanılabilirlik revizyonu | Bekliyor |
| S-233 | ERP/Fintech/Global Intel ürün paketi tanımı | Bekliyor |
| S-234 | Paket bazlı rollout checklist | Bekliyor |

### Teknik Borç (TECHNICAL_AUDIT_2026-03-20'den)
| Öncelik | Konu | Durum |
|---|---|---|
| P0 | Multi-tenant isolation hardening | Açık |
| P0 | Migration safety guardrails (dry-run, backup checkpoint) | Açık |
| P0 | Permission change audit events | Açık |
| P1 | Finance: recurring transactions, budget vs actual | Açık |
| P1 | Inventory: supplier/reorder workflow | Açık |
| P1 | Reporting engine: PDF/Excel + signed exports | Açık |
| P2 | Notification engine (email/WhatsApp queue) | Açık |
| P2 | Dashboard realtime (SSE/WebSocket) | Açık |

---

## Yönetim Prensipleri

1. **Main'e doğrudan commit yok.** Her iş `23martclaude` üzerinde geliştirilir.
2. **Her değişiklik önce test edilir.** Security gate (`bandit`, `pip-audit`, `unittest`) geçmeden PR açılmaz.
3. **Sprint 2.3 önce bitirilir**, sonra P0 teknik borçlar ele alınır.
4. **Blokaj varsa Mustafa Inan'a eskalasyon** – aynı gün.
5. **MASTER_BLUEPRINT.md esas referans** – çelişki durumunda blueprint geçerli.

---

## Sonraki Aksiyonlar

1. Sprint 2.3 taskları başlatmak (S-231 → T-231-1 ve T-231-2)
2. P0 teknik borç kapsamını netleştirmek
3. Faz 3 hazırlık backlog'unu detaylandırmak (S-311, S-312, S-313)
