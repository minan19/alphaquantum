# ESLint Flat-Config Migrasyon Prompt — Alpha Quantum

> **Ne işe yarar:** `next lint` (Next 16'da kaldırılıyor) → ESLint CLI flat-config geçişini,
> bizim yaşadığımız tüm tuzaklardan kaçınarak tek seferde, temiz biçimde yaptırır.
> Bloğu Claude'a yapıştır.

---

## 📋 Yapıştırılacak prompt (kopyala)

```
ROL: Sen kıdemli bir frontend altyapı mühendisisin. Görevin: bir Next.js 15 + ESLint 9
projesinde `next lint`'ten ESLint CLI flat-config'e PROFESYONEL geçiş yapmak. Sonuç
`npm run lint` ile 0 error / 0 warning olmalı ve DAVRANIŞ NÖTR olmalı (eski `next lint`
ile aynı kapsamı/sonucu vermeli).

BAĞLAM
- Frontend dizini: {{FRONTEND_DIR — örn. frontend/}}
- next: ^15.x, eslint-config-next: ^15.x, ESLint: 9.x
- Branch: ayrı bir `chore/eslint-cli-migration` (main'e değil)

KESİN KURALLAR (konvansiyon)
1. Önce çalışma ağacını temizle: `git stash --include-untracked` (alakasız untracked
   dosyalar codemod'u bloklar). İş bitince `git stash pop`.
2. Merge/PR title'da "MERGE ETME" varsa dokunma; merge PO'nun işi.
3. Sadece bu chore'u yap, başka refactor'a girme.

ADIMLAR
A. Codemod'u DOĞRU dizinde koş
   - `cd {{FRONTEND_DIR}}` (codemod repo kökünde "package.json not found" verir;
     Next app frontend/ içindedir).
   - `npx @next/codemod@canary next-lint-to-eslint-cli .`
   - Bu: package.json `"lint": "next lint"` → `"eslint ."` yapar ve `eslint.config.mjs`
     üretir. AMA eski `.eslintrc.json`'ı SİLMEZ ve ürettiği import'lar eslint-config-next
     15.x ile ÇALIŞMAZ (`ERR_MODULE_NOT_FOUND: eslint-config-next/core-web-vitals`).

B. `eslint.config.mjs`'i FlatCompat kalıbıyla DEĞİŞTİR (create-next-app'in ürettiği form)
   - Codemod'un `import ... from "eslint-config-next/core-web-vitals"` satırlarını sil.
   - Yerine:
     import { dirname } from "path";
     import { fileURLToPath } from "url";
     import { FlatCompat } from "@eslint/eslintrc";
     const __dirname = dirname(fileURLToPath(import.meta.url));
     const compat = new FlatCompat({ baseDirectory: __dirname });
     export default [
       { ignores: ["**/.next/**","**/node_modules/**","**/out/**","**/build/**",
                   "**/dist/**","**/coverage/**","next-env.d.ts",
                   "**/*.config.js","**/*.config.mjs","**/*.config.ts","scripts/**"] },
       ...compat.extends("next/core-web-vitals","next/typescript"),
       { rules: { "@typescript-eslint/no-unused-vars": ["warn",{ ignoreRestSiblings: true }] } },
     ];
   - `ignores` KRİTİK: `eslint .` `next lint`'ten farklı olarak .next/, scripts/, config
     dosyalarını da tarar → bunları hariç tutmazsan binlerce sahte hata gelir.
   - Projede `.eslintrc.json`'da özel kural varsa (örn. ignoreRestSiblings) flat config'e
     TAŞI, kaybetme.

C. Gereksiz @eslint/eslintrc yoksa kur: `npm i -D @eslint/eslintrc`

D. Ölü eski config'i sil: `rm .eslintrc.json` (flat config varken yok sayılır).

E. ESLint 9 varsayılan olarak `reportUnusedDisableDirectives`'i AÇAR.
   - `npm run lint` "Unused eslint-disable directive" uyarısı verirse, ilgili
     `// eslint-disable-next-line ...` yorumları gerçekten ölüdür (rule zaten tetiklemiyor).
   - Bunları kaynaktan SİL (gizleme/kapatma; ölü yorumları temizle).

F. Doğrula (FRONTEND_DIR içinde):
   - `npm run lint`      → 0 error / 0 warning
   - `npm run typecheck` → temiz
   - `npm run build`     → derleme yeşil (asıl CI kapısı)

ÇIKTI
- Değişen dosyaların kısa özeti + `npm run lint`/`typecheck` sonuçları.
- Commit (branch'te): `chore(eslint): next lint -> ESLint CLI flat-config (0/0)`.
- PO için PR/merge adımları. Merge'i SEN yapma.

DÜRÜSTLÜK: 0/0 alamadıysan hangi dosyada ne kaldığını yaz; sahte "yeşil" deme.
```

---

## Notlar
- Bu prompt, Alpha Quantum'da yapılan gerçek migrasyondan türetildi (yaşanan 3 tuzak:
  yanlış dizin, codemod'un bozuk import'ları, `eslint .` geniş kapsamı).
- Sürümler değişirse (Next 16'ya çıkınca eslint-config-next flat config'i native destekler)
  B adımındaki FlatCompat köprüsü gereksizleşebilir — o zaman codemod çıktısı doğrudan çalışır.
