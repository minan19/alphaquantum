# Alpha Quantum Frontend

Next.js 15 + React 19 + TypeScript + Tailwind CSS skeleton (S-362).

## Yapı

```
app/
├── layout.tsx              global root (AuthProvider sarılır)
├── page.tsx                "/" → logged in ise /dashboard, değilse /login
├── login/page.tsx          giriş formu (POST /api/v1/auth/login)
├── (app)/                  protected segment (login zorunlu)
│   ├── layout.tsx          Sidebar + ProtectedRoute
│   ├── dashboard/page.tsx  live signals
│   ├── customers/page.tsx  CRM listesi + KVKK consent rozetleri
│   └── invoices/page.tsx   fatura listesi + açık bakiye
components/
├── sidebar.tsx             navigasyon
└── protected-route.tsx     auth guard
lib/
├── api.ts                  fetch wrapper + tipli endpoint helpers
└── auth-context.tsx        React context, localStorage JWT
```

## Yerel geliştirme

```bash
cd frontend
cp .env.example .env.local         # NEXT_PUBLIC_API_BASE_URL ayarla
npm install
npm run dev                        # http://localhost:3000
```

API backend ayrı çalışır olmalı (`docker compose up` veya `uvicorn main:app`).

## Docker

```bash
docker build -t alphaquantum-frontend .
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
  alphaquantum-frontend
```

Veya `docker/docker-compose.yml`'in `frontend` servisi üzerinden.

## Auth akışı

1. `/login` → kullanıcı `POST /api/v1/auth/login` çağırır
2. JWT `localStorage["aq.access_token"]`'a yazılır
3. `AuthProvider` her sayfa render'ında bu token'ı okur
4. `ProtectedRoute` ile sarılı sayfalar `isAuthenticated=false` ise `/login`'e atar
5. `apiRequest()` her isteğe otomatik `Authorization: Bearer <token>` ekler

## Sıradakiler (gelecek sprint'ler)

- [ ] Server-side auth (cookie tabanlı, refresh token)
- [ ] Form validation (zod / react-hook-form)
- [ ] Tablo sıralama, filtre, sayfalama
- [ ] Notification merkezi (S-334 bildirimleri için)
- [ ] FX summary panel (S-341)
- [ ] Müşteri risk skoru detay sayfası (S-333)
- [ ] Senet/Çek/Bono ekranları (S-342)
- [ ] Tahsilat dispatch UI + delivery log (S-343)
- [ ] Multi-company switcher (header)
- [ ] Tema/dark mode (opsiyonel)
- [ ] E2E test (Playwright)
