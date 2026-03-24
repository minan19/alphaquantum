# Alpha Quantum – Rol Bazlı Dashboard Menü Görünürlük Kuralları

**Sprint:** 2.3 – Task T-231-1
**Tarih:** 24 Mart 2026
**Owner:** Claude (23martclaude branch)

---

## 1. Rol Tanımları

| Rol | Kapsam |
|---|---|
| `admin` | Tüm modüller, tüm şirketler, sistem yönetimi |
| `manager` | Operasyonel modüller (yazma dahil), company scope ile kısıtlı |
| `viewer` | Sadece okuma, company scope ile kısıtlı |

---

## 2. Menü / Bölüm Görünürlük Matrisi

| Dashboard Bölümü | admin | manager | viewer | İzin Adı |
|---|---|---|---|---|
| **KPI Özet Kartları** | ✅ | ✅ | ✅ | `read_companies` |
| **Şirket Kartları** | ✅ | ✅ | ✅ | `read_companies` |
| **AI Insights Paneli** | ✅ | ✅ | ✅ | `read_companies` |
| **Piyasa Sinyali Paneli** | ✅ | ✅ | ✅ | `read_market` |
| **Simulate Butonu** | ✅ | ✅ | ❌ | `run_simulation` |
| **Finance Ledger / Cashflow** | ✅ | ✅ | ✅ | `read_finance` |
| **Finance Yazma (Ledger POST)** | ✅ | ✅ | ❌ | `write_finance` |
| **Market Refresh** | ✅ | ✅ | ❌ | `refresh_market` |
| **Global Intel Paneli** | ✅ | ✅ | ✅ | `read_global_intel` |
| **Kamu Kaynakları / Tender** | ✅ | ✅ | ✅ | `read_public_sources` |
| **Tender Dossier Oluştur** | ✅ | ✅ | ❌ | `prepare_tender_docs` |
| **Procurement Talep Listesi** | ✅ | ✅ | ✅ | `read_procurement` |
| **Procurement Yeni Talep / PO** | ✅ | ✅ | ❌ | `write_procurement` |
| **Procurement Onay Aksiyonu** | ✅ | ✅ | ❌ | `approve_procurement` |
| **Fizibilite Rapor Listesi** | ✅ | ✅ | ✅ | `read_feasibility` |
| **Fizibilite Rapor Oluştur** | ✅ | ✅ | ❌ | `write_feasibility` |
| **Uluslararası Proje Listesi** | ✅ | ✅ | ✅ | `read_international` |
| **Uluslararası Proje Oluştur** | ✅ | ✅ | ❌ | `write_international` |
| **Holding / İştirak Listesi** | ✅ | ✅ | ✅ | `read_holdings` |
| **Holding Yönetimi / Onboard** | ✅ | ✅ | ❌ | `manage_holdings` |
| **Connector Listesi** | ✅ | ✅ | ✅ | `read_connectors` |
| **Connector Yönetimi / Sync** | ✅ | ✅ | ❌ | `manage_connectors` |
| **Kullanıcı Yönetimi** | ✅ | ❌ | ❌ | `manage_users` |
| **Rol Yönetimi** | ✅ | ❌ | ❌ | `manage_roles` |
| **Audit Log** | ✅ | ❌ | ❌ | `read_audit_log` |
| **Migration Yönetimi** | ✅ | ❌ | ❌ | `manage_migrations` |
| **Ecosystem Activate** | ✅ | ✅ | ❌ | `write_feasibility` + `write_international` |

---

## 3. Company Scope Kısıtı

`manager` ve `viewer` rolleri için `company_scopes` alanı ek filtre uygular:

| scope_mode | Etki |
|---|---|
| `holding` veya `["*"]` | Tüm şirketlere erişim |
| `multi` | Listede tanımlı şirketlere erişim |
| `single` | Yalnızca tek şirkete erişim |

- Admin her zaman `*` kapsamlıdır; scope kısıtı uygulanmaz.
- Scope dışı şirket verisine erişim `403 Forbidden` döner.

---

## 4. Dashboard UI Uygulama Kuralları

1. Token yüklendiğinde kullanıcı rolü `localStorage.aq_role` veya API `/api/v1/auth/me` ile alınır.
2. `run_simulation` izni yoksa **Simulate** butonu DOM'dan çıkarılır (gizlenmez, silinir).
3. Yazma aksiyon butonları (`write_*`, `manage_*`) izin yoksa render edilmez.
4. Viewer için Finance/Procurement/Feasibility/International bölümleri read-only moda girer; form panelleri açılmaz.
5. Admin-only bölümler (Kullanıcı/Rol/Audit/Migration) viewer ve manager navigasyonunda görünmez.

---

## 5. Referans

- İzin matrisi: `app/identity_repository.py` → `DEFAULT_ROLE_PERMISSIONS`
- Endpoint koruması: `app/security.py` → `require_permissions()`
- Scope koruması: `app/identity_repository.py` → `check_company_scope()`
