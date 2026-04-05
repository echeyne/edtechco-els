import { useState, useRef, useEffect, useMemo } from "react";
import { cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";

export interface FilterableSelectOption {
  value: string;
  label: string;
}

interface FilterableSelectProps {
  options: FilterableSelectOption[];
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  id?: string;
}

export function FilterableSelect({
  options,
  value,
  onValueChange,
  placeholder = "Select…",
  id,
}: FilterableSelectProps) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(
    () =>
      filter
        ? options.filter((o) =>
            o.label.toLowerCase().includes(filter.toLowerCase()),
          )
        : options,
    [options, filter],
  );

  const selectedLabel = options.find((o) => o.value === value)?.label;

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
        setFilter("");
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Focus input when opened
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  return (
    <div ref={containerRef} className="relative" id={id}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background",
          "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
          !selectedLabel && "text-muted-foreground",
        )}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="truncate">{selectedLabel ?? placeholder}</span>
        <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md">
          <div className="p-2">
            <input
              ref={inputRef}
              type="text"
              className="flex h-8 w-full rounded-md border border-input bg-background px-2 text-sm outline-none placeholder:text-muted-foreground"
              placeholder="Filter…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              aria-label="Filter options"
            />
          </div>
          <ul role="listbox" className="max-h-60 overflow-y-auto px-1 pb-1">
            {filtered.length === 0 && (
              <li className="px-2 py-1.5 text-sm text-muted-foreground">
                No results
              </li>
            )}
            {filtered.map((o) => (
              <li
                key={o.value}
                role="option"
                aria-selected={o.value === value}
                className={cn(
                  "cursor-pointer rounded-sm px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground",
                  o.value === value && "bg-accent text-accent-foreground",
                )}
                onClick={() => {
                  onValueChange(o.value);
                  setOpen(false);
                  setFilter("");
                }}
              >
                {o.label}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
