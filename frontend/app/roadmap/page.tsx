"use client";

/**
 * BZ3: Public roadmap voting + idea submission.
 *
 * Görsel hiyerarşi:
 *   * Hero: "Yol haritamızı sen şekillendir"
 *   * Status filter (idea/planned/in_progress/shipped)
 *   * Item grid: vote button (toggle) + status badge
 *   * "Fikrini paylaş" form (auth gerektirir)
 *
 * Aidiyet hissi:
 *   * Oy ver → upvotes anında artar
 *   * Yeni fikir öner → 30 saniyede yayında
 *   * Status değişince LLM-like Türkçe görsel feedback
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  ChevronUp,
  Lightbulb,
  Loader2,
  Plus,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import {
  fetchCommunityStats,
  fetchRoadmap,
  ROADMAP_CATEGORY_LABEL,
  ROADMAP_STATUS_LABEL,
  ROADMAP_STATUS_TONE,
  submitRoadmapIdea,
  voteOnRoadmap,
  type CommunityStats,
  type RoadmapCategory,
  type RoadmapItem,
  type RoadmapStatus,
} from "@/lib/community-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";


const STATUS_TABS: Array<{ value: RoadmapStatus | "all"; label: string }> = [
  { value: "all", label: "Hepsi" },
  { value: "idea", label: "Fikirler" },
  { value: "planned", label: "Planlandı" },
  { value: "in_progress", label: "Üretimde" },
  { value: "shipped", label: "Yayınlandı" },
];


export default function RoadmapPage() {
  const [items, setItems] = useState<RoadmapItem[]>([]);
  const [stats, setStats] = useState<CommunityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<RoadmapStatus | "all">("all");
  const [voting, setVoting] = useState<number | null>(null);
  const [submitOpen, setSubmitOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, st] = await Promise.all([
        fetchRoadmap({
          status: statusFilter === "all" ? undefined : statusFilter,
          limit: 100,
        }),
        fetchCommunityStats().catch(() => null),
      ]);
      setItems(list.items);
      setStats(st);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { void load(); }, [load]);

  async function handleVote(item: RoadmapItem) {
    setVoting(item.id);
    try {
      const result = await voteOnRoadmap(item.id);
      setItems((prev) =>
        prev.map((it) =>
          it.id === item.id
            ? { ...it, has_voted: result.voted, upvotes: result.upvotes_after }
            : it,
        ),
      );
      toast.success(
        result.voted ? "Oyun alındı 🙌" : "Oyun geri çekildi",
      );
    } catch (err) {
      toast.error("Oy verilemedi", {
        description:
          err instanceof Error ? err.message : "Önce giriş yap",
      });
    } finally {
      setVoting(null);
    }
  }

  return (
    <div className="min-h-screen bg-aq-void text-foreground">
      <div className="max-w-5xl mx-auto px-6 py-12">
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
          className="flex items-end justify-between gap-4 flex-wrap"
        >
          <div>
            <Badge tone="primary" withDot>Yol Haritası</Badge>
            <h1 className="mt-3 text-4xl font-bold tracking-tight">
              Yol haritamızı{" "}
              <span className="bg-gradient-to-r from-aq-quantum-2 to-aq-plasma bg-clip-text text-transparent">
                sen
              </span>{" "}
              şekillendir
            </h1>
            <p className="mt-2 text-aq-dust max-w-xl">
              Fikirlere oy ver, en çok oy alanlar üretim sırasına girer.
              Eksik gördüklerini öner — Alpha Quantum topluluğu kararı verir.
            </p>
            {stats && (
              <div className="flex flex-wrap gap-3 mt-4">
                <StatPill label="açık fikir" value={stats.open_ideas} />
                <StatPill label="planda" value={stats.planned} />
                <StatPill label="üretimde" value={stats.in_progress} />
                <StatPill label="toplam oy" value={stats.total_votes} />
              </div>
            )}
          </div>
          <Button onClick={() => setSubmitOpen(true)}>
            <Plus className="h-4 w-4" />
            Fikrini paylaş
          </Button>
        </motion.header>

        {/* Status tabs */}
        <div className="flex flex-wrap gap-2 mt-8 mb-6">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setStatusFilter(tab.value)}
              className={cn(
                "px-3 py-1.5 rounded-full text-xs transition-colors",
                statusFilter === tab.value
                  ? "bg-aq-quantum/20 text-aq-quantum-2 border border-aq-quantum/30"
                  : "bg-aq-orbital/40 text-aq-dust border border-aq-mist/30 hover:border-aq-mist/60",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Items */}
        {loading && (
          <div className="flex items-center justify-center py-12 text-aq-dust">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            Roadmap yükleniyor…
          </div>
        )}

        {!loading && items.length === 0 && (
          <Card className="p-8 text-center" variant="glass">
            <Lightbulb className="h-8 w-8 mx-auto mb-3 text-aq-dust" />
            <p className="text-sm text-aq-dust">
              Bu kategoride henüz fikir yok. İlki sen ol!
            </p>
            <Button
              size="sm"
              className="mt-3"
              onClick={() => setSubmitOpen(true)}
            >
              <Plus className="h-3.5 w-3.5" />
              Fikrini paylaş
            </Button>
          </Card>
        )}

        <div className="space-y-3">
          {items.map((it, idx) => (
            <RoadmapCard
              key={it.id}
              item={it}
              index={idx}
              onVote={() => void handleVote(it)}
              isVoting={voting === it.id}
            />
          ))}
        </div>

        {/* Submit modal */}
        <AnimatePresence>
          {submitOpen && (
            <SubmitIdeaModal
              onClose={() => setSubmitOpen(false)}
              onSubmitted={() => {
                setSubmitOpen(false);
                void load();
              }}
            />
          )}
        </AnimatePresence>
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


function RoadmapCard({
  item,
  index,
  onVote,
  isVoting,
}: {
  item: RoadmapItem;
  index: number;
  onVote: () => void;
  isVoting: boolean;
}) {
  const tone = ROADMAP_STATUS_TONE[item.status];
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.025 * index }}
    >
      <Card variant="glass" className="p-4">
        <div className="flex items-start gap-3">
          {/* Vote button */}
          <button
            type="button"
            onClick={onVote}
            disabled={isVoting || item.status === "shipped" || item.status === "declined"}
            aria-pressed={item.has_voted}
            className={cn(
              "shrink-0 grid place-items-center w-12 h-14 rounded-md border transition-all",
              item.has_voted
                ? "border-aq-quantum/50 bg-aq-quantum/15 text-aq-quantum-2"
                : "border-aq-mist/40 bg-aq-orbital/40 text-aq-dust hover:border-aq-quantum/30 hover:text-aq-quantum-2",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {isVoting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <ChevronUp className="h-3.5 w-3.5" />
                <span className="text-sm font-bold num">{item.upvotes}</span>
              </>
            )}
          </button>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Badge tone={tone}>{ROADMAP_STATUS_LABEL[item.status]}</Badge>
              <span className="text-[10px] uppercase tracking-wider text-aq-trace">
                {ROADMAP_CATEGORY_LABEL[item.category as RoadmapCategory] ?? item.category}
              </span>
              {item.target_quarter && (
                <span className="text-[10px] text-aq-quantum-2 ml-auto">
                  Hedef: {item.target_quarter}
                </span>
              )}
            </div>
            <h3 className="text-sm font-semibold">{item.title}</h3>
            {item.description && (
              <p className="mt-1 text-xs text-aq-dust line-clamp-2">
                {item.description}
              </p>
            )}
            {item.submitter && (
              <p className="mt-1.5 text-[10px] text-aq-trace">
                @{item.submitter} önerdi
              </p>
            )}
          </div>
        </div>
      </Card>
    </motion.div>
  );
}


function SubmitIdeaModal({
  onClose,
  onSubmitted,
}: {
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<RoadmapCategory>("feature");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    if (!title.trim()) {
      toast.error("Başlık gerekli");
      return;
    }
    setSubmitting(true);
    try {
      await submitRoadmapIdea({
        title: title.trim(),
        description: description.trim(),
        category,
      });
      toast.success("Fikrin yayında 🎯", {
        description: "Topluluk oylayabilir ve görüş bildirebilir",
      });
      onSubmitted();
    } catch (err) {
      toast.error("Fikrin gönderilemedi", {
        description:
          err instanceof Error ? err.message : "Önce giriş yap",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 grid place-items-center bg-aq-void/80 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, y: 12 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.95, y: 12 }}
        transition={{ duration: 0.2 }}
        className="w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <Card className="p-6" variant="glass">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="h-5 w-5 text-aq-quantum-2" />
            <h2 className="text-lg font-bold">Fikrini paylaş</h2>
          </div>
          <p className="text-xs text-aq-dust mb-4">
            Eksik gördüğün özelliği topluluğa öner. Diğer kullanıcılar
            oylar, en çok oy alanlar üretim sırasına girer.
          </p>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-aq-trace block mb-1">
                Başlık <span className="text-aq-fission">*</span>
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={140}
                placeholder="Örn: Stripe ödeme entegrasyonu"
                className="w-full rounded-md border border-aq-mist/40 bg-aq-orbital/60 px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:border-aq-quantum/40"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-aq-trace block mb-1">
                Açıklama
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                maxLength={2000}
                placeholder="Bu özellik neden faydalı? Hangi sorunu çözer?"
                className="w-full rounded-md border border-aq-mist/40 bg-aq-orbital/60 px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:border-aq-quantum/40 resize-none"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-aq-trace block mb-1.5">
                Kategori
              </label>
              <div className="grid grid-cols-3 gap-1.5">
                {(Object.entries(ROADMAP_CATEGORY_LABEL) as Array<[RoadmapCategory, string]>).map(([k, v]) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setCategory(k)}
                    className={cn(
                      "px-2 py-1.5 text-[11px] rounded-md border transition-colors",
                      category === k
                        ? "border-aq-quantum/40 bg-aq-quantum/10 text-aq-quantum-2"
                        : "border-aq-mist/30 bg-aq-orbital/40 text-aq-dust hover:border-aq-mist/50",
                    )}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4 pt-3 border-t border-aq-mist/30">
            <Button variant="ghost" size="sm" onClick={onClose}>
              İptal
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} size="sm">
              {submitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  Gönderiliyor…
                </>
              ) : (
                "Paylaş"
              )}
            </Button>
          </div>
        </Card>
      </motion.div>
    </motion.div>
  );
}
