"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Award,
  Building2,
  Check,
  CreditCard,
  Crown,
  Shield,
  Sparkles,
  Star,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Logomark, Wordmark } from "@/components/brand/logomark";
import { AnimatedCounter } from "@/components/landing/animated-counter";
import { TestimonialCard, type Testimonial } from "@/components/landing/testimonial-card";
import { FAQAccordion, type FAQItem } from "@/components/landing/faq-accordion";
import { StickyDemoCTA } from "@/components/landing/sticky-demo-cta";
import { LogoMarquee } from "@/components/landing/logo-marquee";
import { cn } from "@/lib/cn";

const PARTNER_LOGOS = [
  "Alpha Holding",
  "Beta Tekstil",
  "Gamma İnşaat",
  "Delta Lojistik",
  "Epsilon Gıda",
  "Zeta Kimya",
  "Eta Makina",
  "Theta Enerji",
];

const TESTIMONIALS: Testimonial[] = [
  {
    quote:
      "Üç şirketin nakit akışını tek panelden görebilmek inanılmaz. Gecikmiş alacakların %42'si Alpha Quantum'a geçtikten sonra ilk 3 ayda tahsil edildi.",
    authorName: "Mehmet K.",
    authorRole: "Genel Müdür",
    company: "İnşaat Holding",
    metric: "%42 alacak tahsili",
    rating: 5,
  },
  {
    quote:
      "Daha önce Excel'de takip ediyorduk, her ay 2 gün kayıp. FinOS'un vade uyarı motoru kurulduktan sonra hatırlatma için iş gücü harcamıyoruz.",
    authorName: "Ayşe Y.",
    authorRole: "CFO",
    company: "Tekstil Grup",
    metric: "16 saat / ay tasarruf",
    rating: 5,
  },
  {
    quote:
      "Müşteri risk skoru sayesinde hangi yeni müşterilere kredi açıp açmayacağımıza veriyle karar veriyoruz. Bir kötü alacak vakası daha yaşamadık.",
    authorName: "Hakan B.",
    authorRole: "Finans Direktörü",
    company: "Toptan Gıda",
    metric: "0 kötü alacak (6 ay)",
    rating: 5,
  },
];

const FAQ_ITEMS: FAQItem[] = [
  {
    category: "Fiyat",
    question: "Ücretsiz deneme nasıl çalışıyor?",
    answer:
      "30 gün boyunca Pro planının tüm özelliklerine erişebilirsiniz. Kredi kartı bilgisi istemiyoruz. Sürenin sonunda ödeme planına geçmediğiniz takdirde hesap otomatik olarak Starter seviyesine düşer; verileriniz silinmez.",
  },
  {
    category: "KVKK",
    question: "Verilerim güvende mi? KVKK uyumlu musunuz?",
    answer:
      "Tüm veriler Türkiye'de (Frankfurt yedek + KVK Kurumu uyumlu data residency) tutulur. KVKK madde 11 kapsamında veri sahibi haklarınızı (görüntüleme, düzeltme, silme) panelden tek tıkla kullanabilirsiniz. Audit log her erişimi izler; aylık güvenlik raporu alabilirsiniz.",
  },
  {
    category: "Modüller",
    question: "CorpOS ve FinOS ayrı ayrı alınabiliyor mu?",
    answer:
      "Evet. Sadece çoklu şirket yönetimi istiyorsanız CorpOS standalone alınabilir. Sadece nakit akışı / tahsilat odaklıysanız FinOS yeter. İki modülü birlikte kullanan müşteriler %20 bundle indirimi alır.",
  },
  {
    category: "Entegrasyon",
    question: "Mevcut sistemlerimle nasıl entegre olur?",
    answer:
      "İlk faz: Excel/CSV ile manuel import, Paraşüt ve Logo için connector mevcut. İkinci faz (Q3 2026): GİB e-fatura, KEP, açık bankacılık (Türk bankaları). API erişimi Enterprise planda dahildir; özel entegrasyon ekibimiz 5 iş günü içinde projelendirir.",
  },
  {
    category: "Onboarding",
    question: "Kurulum ne kadar sürer?",
    answer:
      "Self-service onboarding 10 dakika sürer (şirket bilgisi + ilk kullanıcı). Pro/Enterprise planlarda ücretsiz onboarding görüşmesi (60 dakika, ekran paylaşımı) yapıyoruz — ilk faturayı sistem üzerinden kesip ilk tahsilat hatırlatmasını başlatıyoruz.",
  },
  {
    category: "Destek",
    question: "Bir sorun yaşadığımda destek alma süresi nedir?",
    answer:
      "Starter: 8x5 (iş günü mesai), e-posta · 24 saat ilk yanıt. Pro: 12x6, canlı sohbet + e-posta · 4 saat ilk yanıt. Enterprise: 7x24, adanmış müşteri başarı yöneticisi · 1 saat ilk yanıt + telefon hattı.",
  },
];

const PLANS = [
  {
    id: "starter",
    name: "Starter",
    price: "9.999",
    period: "ay",
    tagline: "Tek şirketli KOBİ için temel",
    accent: "border-aq-mist/40",
    cta: "Demo iste",
    href: "#contact",
    popular: false,
    bullets: [
      "Tek şirket / tek modül",
      "100 müşteriye kadar",
      "200 fatura / ay",
      "E-posta bildirim",
      "Standart raporlama (PDF)",
      "8x5 destek",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: "19.999",
    period: "ay",
    tagline: "Büyüyen KOBİ veya küçük holding",
    accent: "border-aq-quantum/60 shadow-quantum",
    cta: "30 gün ücretsiz dene",
    href: "/login",
    popular: true,
    bullets: [
      "5 şirkete kadar",
      "CorpOS + FinOS modülleri",
      "1.000 müşteri",
      "Sınırsız fatura",
      "WhatsApp + SMS + e-posta",
      "AI tahsilat koçu",
      "Müşteri risk skoru (S-333)",
      "Vade uyarı motoru",
      "Holding dashboard",
      "Premium destek 12x6",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "29.999",
    period: "ay+",
    tagline: "Çoklu şirket holding / kurumsal",
    accent: "border-aq-plasma/40",
    cta: "Satış ekibiyle konuş",
    href: "#contact",
    popular: false,
    bullets: [
      "Sınırsız şirket",
      "Tüm CorpOS + FinOS özellikleri",
      "Sınırsız kullanıcı",
      "Özel onboarding",
      "OAuth2 / SSO",
      "Özel SLA (99.9%)",
      "Adanmış müşteri başarı yöneticisi",
      "API erişimi + webhooks",
      "Özel entegrasyonlar (GİB, UYAP, KEP)",
      "ISO 27001 / SOC 2 belgelendirilebilir kurulum",
      "7x24 destek + uzaktan erişim",
    ],
  },
];

const FEATURES = [
  {
    icon: Building2,
    title: "Multi-Company Yönetim",
    text: "Birden fazla şirketi tek panelden yönetin. Holding-level KPI'lar, şirket karşılaştırma, çapraz raporlama.",
  },
  {
    icon: TrendingUp,
    title: "Nakit Akışı Zekası",
    text: "30/60/90 gün ileriye dönük projeksiyon. Alacak yaşlandırma, FX exposure, stres testi.",
  },
  {
    icon: Sparkles,
    title: "AI Tahsilat Koçu",
    text: "Her müşteri için optimum kanal, ton ve saat önerisi. WhatsApp müzakere botu (gelecek).",
  },
  {
    icon: Shield,
    title: "KVKK Uyumlu Tasarım",
    text: "Veri sahibi hakları (export, silme, consent) baştan tasarlandı. KVK Kurumu uyumluluk.",
  },
  {
    icon: Zap,
    title: "Vade Uyarı Motoru",
    text: "T-3/T-1 hatırlatma, T+1/T+7/T+14 gecikme alarmları. Otomatik dispatch, audit log.",
  },
  {
    icon: Award,
    title: "Müşteri Risk Skoru",
    text: "Her müşteri için 0-100 ödeme güvenilirlik skoru. Davranışsal analiz, faktörlü açıklama.",
  },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen relative overflow-hidden">
      <div className="mesh-bg" aria-hidden="true" />

      {/* Top nav */}
      <header className="relative z-10 border-b border-aq-mist/40 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <Logomark size={32} />
            <Wordmark />
          </Link>
          <nav className="hidden sm:flex items-center gap-6 text-sm">
            <a href="#features" className="text-aq-dust hover:text-foreground transition-colors">Özellikler</a>
            <a href="#pricing"  className="text-aq-dust hover:text-foreground transition-colors">Fiyatlar</a>
            <a href="#contact"  className="text-aq-dust hover:text-foreground transition-colors">İletişim</a>
          </nav>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/login">Giriş</Link>
            </Button>
            <Button size="sm" asChild>
              <Link href="/login">Ücretsiz Dene</Link>
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative z-10 mx-auto max-w-5xl px-6 py-20 text-center">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.32, 0.72, 0, 1] }}
        >
          <Badge tone="primary" withDot className="mb-6">
            Multi-Company · KVKK Uyumlu · Türkiye odaklı
          </Badge>
          <h1 className="text-5xl sm:text-6xl font-bold tracking-tight leading-[1.05]">
            <span className="bg-gradient-to-r from-aq-quantum-2 via-aq-plasma to-aq-quantum bg-clip-text text-transparent">
              Şirketinizin
            </span>{" "}
            dijital sinir sistemi.
          </h1>
          <p className="mt-6 mx-auto max-w-2xl text-lg text-aq-dust leading-relaxed">
            Holdinginizin tüm şirketlerini tek panelden yönetin · Alacaklarınızı
            bilimle tahsil edin · Nakit akışını önceden görün ·{" "}
            <span className="text-foreground font-medium">CorpOS + FinOS</span> tek platformda.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button size="lg" asChild>
              <Link href="/login">
                Hemen başla <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button size="lg" variant="secondary" asChild>
              <a href="#features">Özellikleri gör</a>
            </Button>
          </div>
          <p className="mt-6 text-xs text-aq-trace font-mono">
            30 gün ücretsiz · kart bilgisi istemez · KVKK aydınlatma metni
          </p>
        </motion.div>
      </section>

      {/* Pricing cards */}
      <section id="pricing" className="relative z-10 mx-auto max-w-7xl px-6 py-12">
        <div className="text-center mb-12">
          <Badge tone="primary" className="mb-3">Fiyatlandırma</Badge>
          <h2 className="text-3xl font-bold tracking-tight">İhtiyacınıza göre seçin</h2>
          <p className="mt-2 text-sm text-aq-dust">
            Şeffaf fiyat · gizli ücret yok · istediğinizde iptal
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {PLANS.map((p, i) => (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, delay: i * 0.08, ease: [0.32, 0.72, 0, 1] }}
              className={cn(
                "relative rounded-xl border bg-card p-6 flex flex-col",
                p.accent,
                p.popular && "lg:scale-105 lg:-mt-2 lg:-mb-2",
              )}
            >
              {p.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge tone="primary" withDot>
                    <Crown className="h-3 w-3 mr-1" />
                    En popüler
                  </Badge>
                </div>
              )}
              <div>
                <h3 className="text-xl font-bold">{p.name}</h3>
                <p className="mt-1 text-xs text-aq-dust">{p.tagline}</p>
              </div>
              <div className="mt-6 flex items-baseline gap-1.5">
                <span className="text-4xl font-bold tabular num">{p.price}</span>
                <span className="text-xl text-aq-dust">₺</span>
                <span className="text-sm text-aq-trace">/ {p.period}</span>
              </div>
              <Button
                size="lg"
                variant={p.popular ? "primary" : "secondary"}
                className="mt-6 w-full"
                asChild
              >
                <Link href={p.href}>{p.cta}</Link>
              </Button>
              <ul className="mt-6 space-y-2.5 flex-1">
                {p.bullets.map((b) => (
                  <li key={b} className="flex items-start gap-2.5 text-sm">
                    <Check className={cn(
                      "h-4 w-4 shrink-0 mt-0.5",
                      p.popular ? "text-aq-quantum-2" : "text-aq-fusion",
                    )} />
                    <span className={cn("text-aq-dust", p.popular && "text-foreground/90")}>
                      {b}
                    </span>
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>

        {/* Custom plan note */}
        <div className="mt-12 text-center text-sm text-aq-dust">
          <p>
            10+ şirket veya özel ihtiyaçlar için{" "}
            <a href="#contact" className="text-aq-quantum-2 hover:text-aq-plasma">
              özelleştirilmiş plan
            </a>{" "}
            sunuyoruz.
          </p>
        </div>
      </section>

      {/* Features grid */}
      <section id="features" className="relative z-10 mx-auto max-w-7xl px-6 py-20">
        <div className="text-center mb-12">
          <Badge tone="primary" className="mb-3">Neden Alpha Quantum?</Badge>
          <h2 className="text-3xl font-bold tracking-tight">
            {`Türk KOBİ'lerinin ihtiyacı için sıfırdan tasarlandı`}
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.06 }}
              className="rounded-xl border border-aq-mist/40 bg-card/50 p-5"
            >
              <div className="grid h-10 w-10 place-items-center rounded-lg bg-gradient-to-br from-aq-quantum/15 to-aq-plasma/15 ring-1 ring-aq-quantum/25">
                <f.icon className="h-5 w-5 text-aq-quantum-2" />
              </div>
              <h3 className="mt-4 font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm text-aq-dust leading-relaxed">{f.text}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Social proof / trust — animated counters */}
      <section className="relative z-10 mx-auto max-w-5xl px-6 py-16">
        <div className="rounded-2xl border border-aq-mist/40 bg-card/50 p-10">
          <p className="text-center text-[10px] font-mono uppercase tracking-[0.22em] text-aq-trace mb-6">
            Üretim hazır · Test edilmiş · Kurumsal güvenlik
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-8 text-center">
            <StatCounter to={367}  label="Geçen test"           suffix="" />
            <StatCounter to={132}  label="API endpoint"         suffix="+" />
            <StatCounter to={21}   label="Veritabanı migration" suffix="" />
            <StatCounter to={99.9} label="Uptime hedef"          suffix="%" decimals={1} />
          </div>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4 text-xs text-aq-trace font-mono">
            <span className="flex items-center gap-1.5">
              <Shield className="h-3 w-3" /> KVKK
            </span>
            <span>·</span>
            <span className="flex items-center gap-1.5">
              <Star className="h-3 w-3" /> TÜRKPATENT ™
            </span>
            <span>·</span>
            <span className="flex items-center gap-1.5">
              <CreditCard className="h-3 w-3" /> İyzico
            </span>
            <span>·</span>
            <span className="flex items-center gap-1.5">
              <Users className="h-3 w-3" /> Multi-tenant
            </span>
          </div>
        </div>
      </section>

      {/* Customer logo marquee */}
      <LogoMarquee logos={PARTNER_LOGOS} />

      {/* Testimonials */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 py-20">
        <div className="text-center mb-12">
          <Badge tone="primary" className="mb-3">Müşteri Hikayeleri</Badge>
          <h2 className="text-3xl font-bold tracking-tight">
            Patronlar Alpha Quantum ile ne kazandı?
          </h2>
          <p className="mt-2 text-sm text-aq-dust">
            Gerçek müşteriler · gerçek sonuçlar (anonimleştirilmiş referanslar)
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {TESTIMONIALS.map((t, i) => (
            <TestimonialCard key={i} testimonial={t} index={i} />
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section className="relative z-10 mx-auto max-w-3xl px-6 py-20">
        <div className="text-center mb-12">
          <Badge tone="primary" className="mb-3">SSS</Badge>
          <h2 className="text-3xl font-bold tracking-tight">Sıkça sorulan sorular</h2>
          <p className="mt-2 text-sm text-aq-dust">
            Cevabını bulamadınız mı?{" "}
            <a href="mailto:hello@alphaquantum.com.tr" className="text-aq-quantum-2 hover:text-aq-plasma">
              Bize yazın
            </a>
          </p>
        </div>
        <FAQAccordion items={FAQ_ITEMS} defaultOpen="item-0" />
      </section>

      {/* CTA */}
      <section id="contact" className="relative z-10 mx-auto max-w-3xl px-6 py-20 text-center">
        <h2 className="text-3xl font-bold tracking-tight">
          Holdinginizi bilimle yönetin.
        </h2>
        <p className="mt-4 text-aq-dust">
          30 günlük ücretsiz deneme · kart bilgisi istemez · kurulum 10 dakika
        </p>
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Button size="lg" asChild>
            <Link href="/login">
              Hemen başla <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <a href="mailto:hello@alphaquantum.com.tr">Demo iste</a>
          </Button>
        </div>
      </section>

      {/* Sticky demo CTA — appears after scroll */}
      <StickyDemoCTA href="/login" label="Hemen başla" showAfter={800} />

      {/* Footer */}
      <footer className="relative z-10 border-t border-aq-mist/40 mt-16">
        <div className="mx-auto max-w-7xl px-6 py-8 flex flex-wrap items-center justify-between gap-3 text-xs text-aq-trace font-mono">
          <div className="flex items-center gap-3">
            <Logomark size={20} />
            <span>© 2026 Alpha Quantum · CorpOS · FinOS</span>
          </div>
          <div className="flex items-center gap-4">
            <a href="#" className="hover:text-foreground transition-colors">Gizlilik</a>
            <a href="#" className="hover:text-foreground transition-colors">KVKK</a>
            <a href="#" className="hover:text-foreground transition-colors">Kullanım Koşulları</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function StatCounter({
  to, label, suffix = "", prefix = "", decimals = 0,
}: {
  to: number; label: string;
  suffix?: string; prefix?: string; decimals?: number;
}) {
  const formatter = (n: number) =>
    decimals > 0
      ? n.toLocaleString("tr-TR", {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })
      : n.toLocaleString("tr-TR");
  return (
    <div>
      <AnimatedCounter
        to={to}
        prefix={prefix}
        suffix={suffix}
        format={formatter}
        className="text-4xl font-bold bg-gradient-to-r from-aq-quantum-2 to-aq-plasma bg-clip-text text-transparent"
      />
      <div className="mt-1 text-[10px] uppercase tracking-wider text-aq-trace">{label}</div>
    </div>
  );
}
