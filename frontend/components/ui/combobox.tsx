"use client";

/**
 * M1 — Combobox: arama + seçim (Popover içinde liste).
 *
 * Yalnız Radix Popover + standart input/list ile inşa edilmiştir (cmdk gibi ek
 * paket yok). Klavye: yukarı/aşağı ok, Enter, Escape; aria-activedescendant.
 */
import * as React from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/cn";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Input } from "@/components/ui/input";

export interface ComboboxItem {
  value: string;
  label: string;
}

export interface ComboboxProps {
  items: ComboboxItem[];
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  emptyMessage?: string;
  className?: string;
  disabled?: boolean;
}

export function Combobox({
  items,
  value,
  onChange,
  placeholder = "Seç…",
  emptyMessage = "Sonuç yok.",
  className,
  disabled,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [activeIndex, setActiveIndex] = React.useState(0);
  const listboxId = React.useId();

  const filtered = React.useMemo(
    () =>
      items.filter((it) => it.label.toLowerCase().includes(query.toLowerCase())),
    [items, query],
  );

  const selected = items.find((it) => it.value === value);

  React.useEffect(() => {
    if (!open) {
      setQuery("");
      setActiveIndex(0);
    }
  }, [open]);

  const commit = (it: ComboboxItem) => {
    onChange?.(it.value);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          aria-expanded={open}
          aria-haspopup="listbox"
          aria-controls={listboxId}
          className={cn(
            "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background/60 px-3 py-2 text-sm text-foreground",
            "transition-all duration-200 ease-quantum",
            "focus:bg-background/80 focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30",
            "disabled:cursor-not-allowed disabled:opacity-50",
            className,
          )}
        >
          <span className={cn(!selected && "text-muted-foreground")}>
            {selected ? selected.label : placeholder}
          </span>
          <ChevronsUpDown className="h-4 w-4 opacity-50" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0">
        <div className="border-b border-border p-2">
          <Input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ara…"
            aria-controls={listboxId}
            aria-activedescendant={
              filtered[activeIndex] ? `${listboxId}-${filtered[activeIndex].value}` : undefined
            }
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActiveIndex((i) => Math.min(filtered.length - 1, i + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActiveIndex((i) => Math.max(0, i - 1));
              } else if (e.key === "Enter") {
                e.preventDefault();
                if (filtered[activeIndex]) commit(filtered[activeIndex]);
              } else if (e.key === "Escape") {
                setOpen(false);
              }
            }}
            className="h-9"
          />
        </div>
        <ul
          id={listboxId}
          role="listbox"
          className="max-h-60 overflow-y-auto p-1"
        >
          {filtered.length === 0 && (
            <li className="px-2 py-3 text-center text-xs text-muted-foreground">
              {emptyMessage}
            </li>
          )}
          {filtered.map((it, idx) => (
            <li
              key={it.value}
              id={`${listboxId}-${it.value}`}
              role="option"
              aria-selected={value === it.value}
              onMouseEnter={() => setActiveIndex(idx)}
              onClick={() => commit(it)}
              className={cn(
                "flex cursor-pointer items-center justify-between rounded-sm px-2 py-1.5 text-sm text-foreground",
                idx === activeIndex && "bg-accent text-accent-foreground",
              )}
            >
              <span>{it.label}</span>
              {value === it.value && <Check className="h-4 w-4 text-primary" />}
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
