"use client";

import * as Accordion from "@radix-ui/react-accordion";
import { ChevronDown, HelpCircle } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/cn";

export interface FAQItem {
  question: string;
  answer: string;
  /** Optional category badge (e.g. "KVKK", "Fiyat"). */
  category?: string;
}

export function FAQAccordion({
  items,
  defaultOpen,
}: {
  items: FAQItem[];
  /** value of the item to keep open initially. */
  defaultOpen?: string;
}) {
  return (
    <Accordion.Root
      type="single"
      defaultValue={defaultOpen}
      collapsible
      className="divide-y divide-aq-mist/40 overflow-hidden rounded-xl border border-aq-mist/40 bg-card/40"
    >
      {items.map((it, i) => {
        const value = `item-${i}`;
        return (
          <Accordion.Item key={value} value={value} className="group">
            <Accordion.Header className="flex">
              <Accordion.Trigger
                className={cn(
                  "flex flex-1 items-center justify-between gap-4 px-5 py-4 text-left",
                  "text-sm font-medium transition-all duration-200 ease-quantum",
                  "hover:bg-aq-quantum/5",
                  "data-[state=open]:bg-aq-quantum/5",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-aq-quantum/40",
                )}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <HelpCircle className="h-4 w-4 shrink-0 text-aq-quantum-2 opacity-70 group-data-[state=open]:opacity-100" />
                  <span className="truncate">{it.question}</span>
                  {it.category && (
                    <span className="hidden sm:inline-block rounded bg-aq-mist/60 px-1.5 py-0.5 font-mono text-[10px] text-aq-dust">
                      {it.category}
                    </span>
                  )}
                </div>
                <ChevronDown
                  className={cn(
                    "h-4 w-4 shrink-0 text-aq-dust transition-transform duration-300 ease-quantum",
                    "group-data-[state=open]:rotate-180 group-data-[state=open]:text-aq-quantum-2",
                  )}
                />
              </Accordion.Trigger>
            </Accordion.Header>
            <Accordion.Content
              className={cn(
                "overflow-hidden text-sm",
                "data-[state=open]:animate-[accordion-down_300ms_cubic-bezier(0.32,0.72,0,1)]",
                "data-[state=closed]:animate-[accordion-up_300ms_cubic-bezier(0.32,0.72,0,1)]",
              )}
            >
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3, delay: 0.1 }}
                className="px-5 pb-5 pt-1 pl-12 text-aq-dust leading-relaxed"
              >
                {it.answer}
              </motion.div>
            </Accordion.Content>
          </Accordion.Item>
        );
      })}
    </Accordion.Root>
  );
}
