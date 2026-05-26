"use client";

import { motion } from "framer-motion";
import { Quote, Star } from "lucide-react";
import { cn } from "@/lib/cn";

export interface Testimonial {
  quote: string;
  authorName: string;
  authorRole: string;
  company: string;
  /** Optional avatar URL; falls back to initials. */
  avatarUrl?: string;
  /** 1-5 star rating; defaults to 5. */
  rating?: number;
  /** Highlighted metric (e.g. "Alacaklar %42 azaldı"). Shown as a chip. */
  metric?: string;
}

export function TestimonialCard({
  testimonial,
  index = 0,
  variant = "default",
}: {
  testimonial: Testimonial;
  index?: number;
  variant?: "default" | "compact";
}) {
  const initials = testimonial.authorName
    .split(" ")
    .map((s) => s[0])
    .slice(0, 2)
    .join("");
  const rating = testimonial.rating ?? 5;

  return (
    <motion.figure
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.6, delay: index * 0.08, ease: [0.32, 0.72, 0, 1] }}
      className={cn(
        "relative rounded-xl border border-aq-mist/40 bg-card/60 p-6",
        "backdrop-blur-sm transition-all duration-300 ease-quantum",
        "hover:border-aq-quantum/40 hover:bg-card/80 hover:shadow-quantum",
        variant === "compact" && "p-5",
      )}
    >
      {/* Quote mark watermark */}
      <Quote
        className="absolute right-4 top-4 h-8 w-8 text-aq-quantum/15"
        aria-hidden="true"
      />

      {/* Stars */}
      <div className="flex gap-0.5 mb-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Star
            key={i}
            className={cn(
              "h-4 w-4",
              i < rating
                ? "text-aq-solar fill-aq-solar"
                : "text-aq-mist fill-aq-mist",
            )}
          />
        ))}
      </div>

      {/* Quote */}
      <blockquote
        className={cn(
          "text-sm leading-relaxed text-foreground/90 mb-5",
          variant === "default" && "text-base",
        )}
      >
        &ldquo;{testimonial.quote}&rdquo;
      </blockquote>

      {/* Metric chip (optional, conversion booster) */}
      {testimonial.metric && (
        <div className="mb-5 inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-aq-quantum/15 to-aq-plasma/15 px-3 py-1 ring-1 ring-aq-quantum/30">
          <span className="text-xs font-mono font-medium text-aq-quantum-2">
            {testimonial.metric}
          </span>
        </div>
      )}

      {/* Author */}
      <figcaption className="flex items-center gap-3">
        <div
          className={cn(
            "grid h-10 w-10 place-items-center rounded-full overflow-hidden",
            "bg-gradient-to-br from-aq-quantum to-aq-plasma text-white text-xs font-semibold",
            "ring-2 ring-aq-quantum/30 shadow-quantum",
          )}
        >
          {testimonial.avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={testimonial.avatarUrl}
              alt={testimonial.authorName}
              className="h-full w-full object-cover"
            />
          ) : (
            initials
          )}
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold truncate">{testimonial.authorName}</div>
          <div className="text-xs text-aq-dust truncate">
            {testimonial.authorRole} ·{" "}
            <span className="text-aq-quantum-2">{testimonial.company}</span>
          </div>
        </div>
      </figcaption>
    </motion.figure>
  );
}
