"use client";

/**
 * M1 — Date picker. react-day-picker'i Popover içinde gösterir.
 * Semantic class'lar; modül cascade'i otomatik yansır.
 */
import * as React from "react";
import { DayPicker, type DayPickerProps } from "react-day-picker";
import { format } from "date-fns";
import { tr } from "date-fns/locale";
import { Calendar as CalendarIcon } from "lucide-react";
import "react-day-picker/style.css";
import { cn } from "@/lib/cn";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export interface DatePickerProps {
  value?: Date;
  onChange?: (date: Date | undefined) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export function DatePicker({ value, onChange, placeholder = "Tarih seç…", disabled, className }: DatePickerProps) {
  const [open, setOpen] = React.useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            "inline-flex h-10 w-full items-center justify-start gap-2 rounded-md border border-input bg-background/60 px-3 py-2 text-sm text-foreground",
            "transition-all duration-200 ease-quantum",
            "focus:bg-background/80 focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30",
            "disabled:cursor-not-allowed disabled:opacity-50",
            !value && "text-muted-foreground",
            className,
          )}
        >
          <CalendarIcon className="h-4 w-4 opacity-60" />
          {value ? format(value, "PPP", { locale: tr }) : placeholder}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={value}
          onSelect={(d: Date | undefined) => {
            onChange?.(d);
            setOpen(false);
          }}
          locale={tr}
        />
      </PopoverContent>
    </Popover>
  );
}

/** react-day-picker v9 wrapper. v9 default stilini tutar; semantic class'lar
 *  Popover'dan miras alınır (bg-popover, text-foreground). v9'un sınıf adı
 *  şeması v8'den farklı; daha sıkı stil özelleştirmesi yapmak yerine default
 *  stilini bırakıyoruz (popover içinde token'lar zaten doğru cascade'liyor). */
export function Calendar(props: DayPickerProps) {
  return <DayPicker {...props} className="p-3" />;
}
