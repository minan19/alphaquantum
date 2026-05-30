"use client";

/**
 * BZ3: Public changelog timeline.
 *
 * Görsel hiyerarşi:
 *   * Hero: "Şu ana kadar X özellik yayınlandı" canlı sayaç
 *   * Vertical timeline: her release bir kart
 *   * Kategori filtreleri
 *   * Trust by design: gerçek release tarihleri + version no'ları
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Shield,
  Sparkles,
  Wrench,
  Zap,
} from "lucide-react";
import {
  CHANGELOG_CATEGORY_LABEL,
  CHANGELOG_CATEGORY_TONE,
  fetchChangelog,
  fetchCommunityStats,
  type ChangelogCategory,
  type ChangelogEntry,
  type CommunityStats,
} from "@/lib/community-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";


const CATEGORY_ICONS: Record<ChangelogCategory, typeof Sparkles> = {
  feature: Sparkles,
  fix: Wrench,
  improvement: Zap,
  security: Shield,
};


export default function ChangelogPage() {
  const [entries, setEntries] = useState<ChangelogEntry[]>([]);
  const [stats, setStats] = useState<CommunityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<ChangelogCategory | "all">("all");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [list, st] = await Promise.all([
          fetchChangelog({
            limit: 100,
            category: filter === "all" ? undefined : filter,
          }),
          fetchCommunityStats().catch(() => null),
        ]);
        if (!cancelled) {
          setEntries(list.entries);
          setStats(st);
        }
      } catch {
        if (!cancelled) setEntries([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [filter]);

  return (
    <div className="min-h-screen bg-aq-void text-foreground">
      <div className="max-w-4xl mx-auto px-6 py-12">
        {/* Back link */}
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs text-aq-dust hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft className="h-3 w-3" />
          Ana sayfa
        </Link>

        {/* Hero */}
        <motion.header
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <Badge tone="primary" withDot>Sürüm Notları</Badge>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">
            Alpha Quantum{" "}
            <span className="bg-gradient-to-r from-aq-quantum-2 to-aq-plasma bg-clip-text text-transparent">
              gelişiyor
            </span>
          </h1>
          <p className="mt-2 text-aq-dust max-w-xl">
            Şu ana kadar yayınlanmış tüm özellikler, düzeltmeler ve
            iyileştirmeler. Şeffaflık birinci sınıf.
          </p>
          {stats && (
            <div className="flex flex-wrap gap-3 mt-4">
              <StatPill label="yayınlanan özellik" value={stats.shipped_features} />
              <StatPill label="üretimde" value={stats.in_progress} />
              <StatPill label="kullanıcı oyu" value={stats.total_votes} />
            </div>
          )}
        </motion.header>

        {/* Filter pills */}
        <div className="flex flex-wrap gap-2 mt-8 mb-6">
          <FilterPill
            active={filter === "all"}
            onClick={() => setFilter("all")}
            label="Hepsi"
          />
          {(["feature", "improvement", "fix", "security"] as ChangelogCategory[]).map((c) => (
            <FilterPill
              key={c}
              active={filter === c}
              onClick={() => setFilter(c)}
              label={CHANGELOG_CATEGORY_LABEL[c]}
            />
          ))}
        </div>

        {/* Timeline */}
        {loading && (
          <div className="flex items-center justify-center py-12 text-aq-dust">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            Sürüm notları yükleniyor…
          </div>
        )}

        {!loading && entries.length === 0 && (
          <Card className="p-8 text-center" variant="glass">
            <Sparkles className="h-8 w-8 mx-auto mb-3 text-aq-dust" />
            <p className="text-sm text-aq-dust">
              Bu kategoride henüz yayınlanan özellik yok.
            </p>
          </Card>
        )}

        <div className="space-y-4">
          {entries.map((e, i) => (
            <ChangelogCard key={e.id} entry={e} index={i} />
          ))}
        </div>

        {/* Footer CTA */}
        <div className="mt-12 text-center">
          <p className="text-sm text-aq-dust">
            Bir özellik mi eksik? Roadmap'te oy ver veya öner.
          </p>
          <Link href="/roadmap">
            <Button className="mt-3" size="sm">
              Roadmap'i gör →
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}


function StatPill({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-aq-mist/30 bg-aq-orbital/40 px-3 py-1.5">
      <span className="text-2xl font-bold num text-foreground">{value}</span>
      <span className="text-[10px] text-aq-trace uppercase tracking-wider ml-2">
        {label}
      </span>
    </div>
  );
}


function FilterPill({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "px-3 py-1.5 rounded-full text-xs transition-colors",
        active
          ? "bg-aq-quantum/20 text-aq-quantum-2 border border-aq-quantum/30"
          : "bg-aq-orbital/40 text-aq-dust border border-aq-mist/30 hover:border-aq-mist/60",
      )}
    >
      {label}
    </button>
  );
}


function ChangelogCard({
  entry,
  index,
}: {
  entry: ChangelogEntry;
  index: number;
}) {
  const Icon = CATEGORY_ICONS[entry.category];
  const tone = CHANGELOG_CATEGORY_TONE[entry.category];
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.03 * index }}
    >
      <Card variant="glass" className="p-5">
        <div className="flex items-start gap-4">
          <div className="shrink-0">
            <div
              className={cn(
                "h-9 w-9 rounded-full grid place-items-center",
                "bg-aq-orbital/60 border border-aq-mist/40",
              )}
            >
              <Icon className="h-4 w-4 text-aq-quantum-2" />
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-[11px] text-aq-quantum-2 bg-aq-quantum/10 px-1.5 py-0.5 rounded">
                v{entry.version}
              </span>
              <Badge tone={tone}>{CHANGELOG_CATEGORY_LABEL[entry.category]}</Badge>
              <span className="text-[10px] text-aq-trace ml-auto">
                {new Date(entry.released_at * 1000).toLocaleDateString("tr-TR", {
                  day: "numeric", month: "long", year: "numeric",
                })}
              </span>
            </div>
            <h3 className="text-base font-semibold">{entry.title}</h3>
            {entry.description && (
              <p className="mt-2 text-sm text-aq-dust leading-relaxed">
                {entry.description}
              </p>
            )}
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
