import { useState, useEffect, useCallback, useMemo } from "react";
import type {
  Document,
  Domain,
  DomainWithChildren,
  Strand,
  StrandWithChildren,
  SubStrand,
  SubStrandWithChildren,
  Indicator,
  HierarchyResponse,
} from "@els/shared";
import { getDocuments, getHierarchy, getFilters } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ChevronRight,
  ChevronDown,
  ChevronsDownUp,
  ChevronsUpDown,
  ShieldCheck,
  Search,
  Edit,
  Trash2,
  X,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FilterState {
  country?: string;
  state?: string;
  verificationStatus?: "all" | "verified" | "unverified";
  searchQuery?: string;
}

export interface HierarchyTableProps {
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  onEdit?: (
    record: Domain | Strand | SubStrand | Indicator,
    type: string,
  ) => void;
  onDelete?: (id: number, type: string) => Promise<void>;
  onVerify?: (id: number, type: string, verified: boolean) => Promise<void>;
  onDataLoaded?: (
    documents: Document[],
    hierarchies: Map<number, HierarchyResponse>,
  ) => void;
  /** Pass an updated record to patch it in-place without a full reload */
  updateRecord?: {
    record: Domain | Strand | SubStrand | Indicator;
    type: string;
  } | null;
}

type SortField = "code" | "name" | "status" | "ageBand";
type SortDir = "asc" | "desc";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function matchesSearch(text: string, query: string): boolean {
  return text.toLowerCase().includes(query.toLowerCase());
}

function recordMatchesSearch(
  record: {
    code?: string;
    name?: string;
    title?: string | null;
    description?: string | null;
  },
  query: string,
): boolean {
  if (!query) return true;
  const fields = [
    record.code,
    record.name,
    record.title,
    record.description,
  ].filter(Boolean) as string[];
  return fields.some((f) => matchesSearch(f, query));
}

function matchesVerification(
  humanVerified: boolean,
  status: "all" | "verified" | "unverified" | undefined,
): boolean {
  if (!status || status === "all") return true;
  return status === "verified" ? humanVerified : !humanVerified;
}

/** Return a compare value for sorting. */
function compareField(
  a: string | boolean,
  b: string | boolean,
  dir: SortDir,
): number {
  if (typeof a === "boolean" && typeof b === "boolean") {
    const diff = (a ? 1 : 0) - (b ? 1 : 0);
    return dir === "asc" ? diff : -diff;
  }
  const diff = String(a).localeCompare(String(b));
  return dir === "asc" ? diff : -diff;
}

// ---------------------------------------------------------------------------
// VerifiedBadge
// ---------------------------------------------------------------------------

function VerifiedBadge({
  verified,
  onClick,
}: {
  verified: boolean;
  onClick?: () => void;
}) {
  const badge = verified ? (
    <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100 shadow-none">
      <ShieldCheck className="mr-1 h-3 w-3" />
      Verified
    </Badge>
  ) : (
    <Badge variant="secondary" className="text-muted-foreground shadow-none">
      Unverified
    </Badge>
  );

  if (onClick) {
    return (
      <button
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
        className="cursor-pointer hover:opacity-80"
        aria-label={verified ? "Mark as unverified" : "Mark as verified"}
      >
        {badge}
      </button>
    );
  }

  return badge;
}

// ---------------------------------------------------------------------------
// ExpandToggle
// ---------------------------------------------------------------------------

function ExpandToggle({
  expanded,
  onToggle,
  depth,
}: {
  expanded: boolean;
  onToggle: () => void;
  depth: number;
}) {
  return (
    <button
      onClick={onToggle}
      className="inline-flex items-center hover:text-foreground text-muted-foreground"
      style={{ paddingLeft: `${depth * 1.5}rem` }}
      aria-label={expanded ? "Collapse" : "Expand"}
    >
      {expanded ? (
        <ChevronDown className="h-4 w-4" />
      ) : (
        <ChevronRight className="h-4 w-4" />
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// ActionButtons
// ---------------------------------------------------------------------------

function ActionButtons({
  onEdit,
  onDelete,
}: {
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  return (
    <div className="flex items-center gap-1">
      {onEdit && (
        <Button variant="ghost" size="icon" onClick={onEdit} aria-label="Edit">
          <Edit className="h-4 w-4" />
        </Button>
      )}
      {onDelete && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onDelete}
          aria-label="Delete"
          className="text-destructive hover:text-destructive"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// FilterBar
// ---------------------------------------------------------------------------

function FilterBar({
  filters,
  onFilterChange,
  countries,
  states,
  expandButton,
}: {
  filters: FilterState;
  onFilterChange: (f: FilterState) => void;
  countries: string[];
  states: string[];
  expandButton?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search standards..."
            value={filters.searchQuery ?? ""}
            onChange={(e) =>
              onFilterChange({ ...filters, searchQuery: e.target.value })
            }
            className="pl-9 pr-8 h-9"
          />
          {filters.searchQuery && (
            <button
              onClick={() => onFilterChange({ ...filters, searchQuery: "" })}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Country */}
          <Select
            value={filters.country ?? "__all__"}
            onValueChange={(v) =>
              onFilterChange({
                ...filters,
                country: v === "__all__" ? undefined : v,
                state: undefined,
              })
            }
          >
            <SelectTrigger className="w-[150px] h-9">
              <SelectValue placeholder="Country" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Countries</SelectItem>
              {countries.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* State */}
          <Select
            value={filters.state ?? "__all__"}
            onValueChange={(v) =>
              onFilterChange({
                ...filters,
                state: v === "__all__" ? undefined : v,
              })
            }
          >
            <SelectTrigger className="w-[150px] h-9">
              <SelectValue placeholder="State" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All States</SelectItem>
              {states.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Verification Status */}
          <Select
            value={filters.verificationStatus ?? "all"}
            onValueChange={(v) =>
              onFilterChange({
                ...filters,
                verificationStatus: v as FilterState["verificationStatus"],
              })
            }
          >
            <SelectTrigger className="w-[150px] h-9">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="verified">Verified</SelectItem>
              <SelectItem value="unverified">Unverified</SelectItem>
            </SelectContent>
          </Select>

          {expandButton}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SortableHeader
// ---------------------------------------------------------------------------

function SortableHeader({
  label,
  field,
  sortField,
  sortDir,
  onSort,
}: {
  label: string;
  field: SortField;
  sortField: SortField;
  sortDir: SortDir;
  onSort: (f: SortField) => void;
}) {
  const active = sortField === field;
  return (
    <button
      className={`inline-flex items-center gap-1 transition-colors ${active ? "text-foreground" : "hover:text-foreground"}`}
      onClick={() => onSort(field)}
    >
      {label}
      {active && (
        <span className="text-xs text-primary">
          {sortDir === "asc" ? "↑" : "↓"}
        </span>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function HierarchyTable({
  filters,
  onFilterChange,
  onEdit,
  onDelete,
  onVerify,
  onDataLoaded,
  updateRecord,
}: HierarchyTableProps) {
  const { hasEditPermission } = useAuth();

  // Data state
  const [documents, setDocuments] = useState<Document[]>([]);
  const [hierarchies, setHierarchies] = useState<
    Map<number, HierarchyResponse>
  >(new Map());

  /** Patch a single record's humanVerified flag in the hierarchy map */
  const patchVerified = useCallback(
    (id: number, type: string, verified: boolean) => {
      setHierarchies((prev) => {
        const next = new Map(prev);
        for (const [docId, h] of next) {
          let changed = false;
          const patchIndicators = (indicators: Indicator[]) =>
            indicators.map((ind) =>
              type === "indicator" && ind.id === id
                ? ((changed = true), { ...ind, humanVerified: verified })
                : ind,
            );
          const newH: HierarchyResponse = {
            ...h,
            domains: h.domains.map((d) => {
              if (type === "domain" && d.id === id) {
                changed = true;
                return { ...d, humanVerified: verified };
              }
              const domainIndicators = patchIndicators(d.indicators);
              const newStrands = d.strands.map((s) => {
                if (type === "strand" && s.id === id) {
                  changed = true;
                  return { ...s, humanVerified: verified };
                }
                const strandIndicators = patchIndicators(s.indicators);
                const newSubStrands = s.subStrands.map((ss) => {
                  if (type === "sub_strand" && ss.id === id) {
                    changed = true;
                    return { ...ss, humanVerified: verified };
                  }
                  const newIndicators = patchIndicators(ss.indicators);
                  return changed ? { ...ss, indicators: newIndicators } : ss;
                });
                return changed
                  ? {
                      ...s,
                      subStrands: newSubStrands,
                      indicators: strandIndicators,
                    }
                  : s;
              });
              return changed
                ? { ...d, strands: newStrands, indicators: domainIndicators }
                : d;
            }),
          };
          if (changed) {
            next.set(docId, newH);
            break;
          }
        }
        return next;
      });
    },
    [],
  );

  /** Remove a record from the hierarchy map by id and type */
  const patchDelete = useCallback((id: number, type: string) => {
    setHierarchies((prev) => {
      const next = new Map(prev);
      const filterIndicators = (indicators: Indicator[]) =>
        indicators.filter((ind) => {
          if (type === "indicator" && ind.id === id) {
            return false;
          }
          return true;
        });
      for (const [docId, h] of next) {
        let changed = false;
        const newH: HierarchyResponse = {
          ...h,
          domains:
            type === "domain"
              ? h.domains.filter((d) => {
                  if (d.id === id) {
                    changed = true;
                    return false;
                  }
                  return true;
                })
              : h.domains.map((d) => {
                  const domainIndicators = filterIndicators(d.indicators);
                  if (domainIndicators.length !== d.indicators.length)
                    changed = true;
                  const newStrands =
                    type === "strand"
                      ? d.strands.filter((s) => {
                          if (s.id === id) {
                            changed = true;
                            return false;
                          }
                          return true;
                        })
                      : d.strands.map((s) => {
                          const strandIndicators = filterIndicators(
                            s.indicators,
                          );
                          if (strandIndicators.length !== s.indicators.length)
                            changed = true;
                          const newSubStrands =
                            type === "sub_strand"
                              ? s.subStrands.filter((ss) => {
                                  if (ss.id === id) {
                                    changed = true;
                                    return false;
                                  }
                                  return true;
                                })
                              : s.subStrands.map((ss) => {
                                  const newIndicators = filterIndicators(
                                    ss.indicators,
                                  );
                                  if (
                                    newIndicators.length !==
                                    ss.indicators.length
                                  )
                                    changed = true;
                                  return newIndicators.length !==
                                    ss.indicators.length
                                    ? { ...ss, indicators: newIndicators }
                                    : ss;
                                });
                          return changed || newSubStrands !== s.subStrands
                            ? {
                                ...s,
                                subStrands: newSubStrands,
                                indicators: strandIndicators,
                              }
                            : s;
                        });
                  return changed || newStrands !== d.strands
                    ? {
                        ...d,
                        strands: newStrands,
                        indicators: domainIndicators,
                      }
                    : d;
                }),
        };
        if (changed) {
          next.set(docId, newH);
          break;
        }
      }
      return next;
    });
  }, []);

  /** Patch a full record update in the hierarchy map */
  useEffect(() => {
    if (!updateRecord) return;
    const { record, type } = updateRecord;
    setHierarchies((prev) => {
      const next = new Map(prev);
      for (const [docId, h] of next) {
        let changed = false;
        const patchIndicators = (indicators: Indicator[]) =>
          indicators.map((ind) =>
            type === "indicator" && ind.id === record.id
              ? ((changed = true), { ...ind, ...(record as Indicator) })
              : ind,
          );
        const newH: HierarchyResponse = {
          ...h,
          domains: h.domains.map((d) => {
            if (type === "domain" && d.id === record.id) {
              changed = true;
              return { ...d, ...(record as Domain) };
            }
            const domainIndicators = patchIndicators(d.indicators);
            const newStrands = d.strands.map((s) => {
              if (type === "strand" && s.id === record.id) {
                changed = true;
                return { ...s, ...(record as Strand) };
              }
              const strandIndicators = patchIndicators(s.indicators);
              const newSubStrands = s.subStrands.map((ss) => {
                if (type === "sub_strand" && ss.id === record.id) {
                  changed = true;
                  return { ...ss, ...(record as SubStrand) };
                }
                const newIndicators = patchIndicators(ss.indicators);
                return changed ? { ...ss, indicators: newIndicators } : ss;
              });
              return changed
                ? {
                    ...s,
                    subStrands: newSubStrands,
                    indicators: strandIndicators,
                  }
                : s;
            });
            return changed
              ? { ...d, strands: newStrands, indicators: domainIndicators }
              : d;
          }),
        };
        if (changed) {
          next.set(docId, newH);
          break;
        }
      }
      return next;
    });
  }, [updateRecord]);

  /** Wrap onVerify to also do an optimistic local patch */
  const handleVerify = useCallback(
    async (id: number, type: string, verified: boolean) => {
      // Optimistic update
      patchVerified(id, type, verified);
      try {
        await onVerify?.(id, type, verified);
      } catch {
        // Revert on failure
        patchVerified(id, type, !verified);
      }
    },
    [onVerify, patchVerified],
  );
  const [countries, setCountries] = useState<string[]>([]);
  const [states, setStates] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [sortField, setSortField] = useState<SortField>("code");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  // ------ Data fetching ------

  const fetchFilters = useCallback(async () => {
    try {
      const f = await getFilters();
      setCountries(f.countries);
      setStates(f.states);
    } catch {
      // non-critical – filters just won't populate
    }
  }, []);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const docs = await getDocuments({
        country: filters.country,
        state: filters.state,
      });
      setDocuments(docs);

      // Fetch hierarchy for each document
      const entries = await Promise.all(
        docs.map(async (doc) => {
          try {
            const h = await getHierarchy(doc.id);
            return [doc.id, h] as const;
          } catch {
            return null;
          }
        }),
      );

      const map = new Map<number, HierarchyResponse>();
      for (const entry of entries) {
        if (entry) map.set(entry[0], entry[1]);
      }
      setHierarchies(map);
      onDataLoaded?.(docs, map);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [filters.country, filters.state, onDataLoaded]);

  useEffect(() => {
    fetchFilters();
  }, [fetchFilters]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  /** Wrap onDelete to do an optimistic local removal */
  const handleDelete = useCallback(
    async (id: number, type: string) => {
      patchDelete(id, type);
      try {
        await onDelete?.(id, type);
      } catch {
        // Re-fetch on failure to restore state
        fetchDocuments();
      }
    },
    [onDelete, patchDelete, fetchDocuments],
  );

  // ------ Expand / collapse ------

  const toggleExpand = useCallback((key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const allExpanded = useMemo(() => {
    const keys: string[] = [];
    for (const doc of documents) {
      keys.push(`doc-${doc.id}`);
      const h = hierarchies.get(doc.id);
      if (!h) continue;
      for (const domain of h.domains) {
        keys.push(`domain-${domain.id}`);
        for (const strand of domain.strands) {
          keys.push(`strand-${strand.id}`);
          for (const ss of strand.subStrands) {
            keys.push(`substrand-${ss.id}`);
          }
        }
      }
    }
    return keys;
  }, [documents, hierarchies]);

  const handleExpandAll = useCallback(() => {
    setExpanded(new Set(allExpanded));
  }, [allExpanded]);

  const handleCollapseAll = useCallback(() => {
    setExpanded(new Set());
  }, []);

  const isAllExpanded =
    allExpanded.length > 0 && allExpanded.every((k) => expanded.has(k));

  // ------ Sorting ------

  const handleSort = useCallback(
    (field: SortField) => {
      if (field === sortField) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortField(field);
        setSortDir("asc");
      }
    },
    [sortField],
  );

  // ------ Build visible rows ------

  const rows = useMemo(() => {
    const result: React.ReactNode[] = [];
    const { verificationStatus, searchQuery } = filters;

    for (const doc of documents) {
      const hierarchy = hierarchies.get(doc.id);
      if (!hierarchy) continue;

      const docKey = `doc-${doc.id}`;
      const docExpanded = expanded.has(docKey);

      // Check if any child matches search / verification filter
      const docMatchesSearch =
        !searchQuery || matchesSearch(doc.title, searchQuery);

      // Sort domains
      const sortedDomains = [...hierarchy.domains].sort((a, b) => {
        if (sortField === "code") return compareField(a.code, b.code, sortDir);
        if (sortField === "name") return compareField(a.name, b.name, sortDir);
        return compareField(a.humanVerified, b.humanVerified, sortDir);
      });

      // Check if doc has any visible children
      let docHasVisibleChildren = docMatchesSearch;
      if (!docHasVisibleChildren) {
        docHasVisibleChildren = sortedDomains.some((domain) =>
          domainHasMatch(domain, searchQuery, verificationStatus),
        );
      }
      if (!docHasVisibleChildren) continue;

      // Document row
      result.push(
        <TableRow
          key={docKey}
          className="bg-primary/5 hover:bg-primary/10 font-medium"
        >
          <TableCell>
            <ExpandToggle
              expanded={docExpanded}
              onToggle={() => toggleExpand(docKey)}
              depth={0}
            />
          </TableCell>
          <TableCell className="font-semibold text-foreground">
            {doc.title}
          </TableCell>
          <TableCell className="text-muted-foreground">
            {doc.country} / {doc.state} - {doc.versionYear}
          </TableCell>
          <TableCell />
          <TableCell />
          <TableCell />
          {hasEditPermission && <TableCell />}
        </TableRow>,
      );

      if (!docExpanded) continue;

      for (const domain of sortedDomains) {
        renderDomain(result, domain, doc.id, searchQuery, verificationStatus);
      }
    }

    return result;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    documents,
    hierarchies,
    expanded,
    filters,
    sortField,
    sortDir,
    hasEditPermission,
    onEdit,
    handleDelete,
    onVerify,
    toggleExpand,
  ]);

  // ------ Recursive render helpers ------

  function domainHasMatch(
    domain: DomainWithChildren,
    query?: string,
    status?: "all" | "verified" | "unverified",
  ): boolean {
    if (
      recordMatchesSearch(domain, query ?? "") &&
      matchesVerification(domain.humanVerified, status)
    )
      return true;
    // Check direct indicators on the domain
    if (
      domain.indicators.some(
        (ind) =>
          recordMatchesSearch(ind, query ?? "") &&
          matchesVerification(ind.humanVerified, status),
      )
    )
      return true;
    return domain.strands.some((s) => strandHasMatch(s, query, status));
  }

  function strandHasMatch(
    strand: StrandWithChildren,
    query?: string,
    status?: "all" | "verified" | "unverified",
  ): boolean {
    if (
      recordMatchesSearch(strand, query ?? "") &&
      matchesVerification(strand.humanVerified, status)
    )
      return true;
    // Check direct indicators on the strand
    if (
      strand.indicators.some(
        (ind) =>
          recordMatchesSearch(ind, query ?? "") &&
          matchesVerification(ind.humanVerified, status),
      )
    )
      return true;
    return strand.subStrands.some((ss) => subStrandHasMatch(ss, query, status));
  }

  function subStrandHasMatch(
    subStrand: SubStrandWithChildren,
    query?: string,
    status?: "all" | "verified" | "unverified",
  ): boolean {
    if (
      recordMatchesSearch(subStrand, query ?? "") &&
      matchesVerification(subStrand.humanVerified, status)
    )
      return true;
    return subStrand.indicators.some(
      (ind) =>
        recordMatchesSearch(ind, query ?? "") &&
        matchesVerification(ind.humanVerified, status),
    );
  }

  function renderDomain(
    result: React.ReactNode[],
    domain: DomainWithChildren,
    docId: number,
    searchQuery?: string,
    verificationStatus?: "all" | "verified" | "unverified",
  ) {
    if (!domainHasMatch(domain, searchQuery, verificationStatus)) return;

    const key = `domain-${domain.id}`;
    const isExpanded = expanded.has(key);

    result.push(
      <TableRow key={key} className="bg-blue-50/60 hover:bg-blue-50">
        <TableCell>
          <ExpandToggle
            expanded={isExpanded}
            onToggle={() => toggleExpand(key)}
            depth={1}
          />
        </TableCell>
        <TableCell>
          <span className="inline-flex items-center gap-2">
            <span className="text-xs font-mono text-primary/70 bg-primary/5 px-1.5 py-0.5 rounded">
              {domain.code}
            </span>
            <span className="font-medium">{domain.name}</span>
          </span>
        </TableCell>
        <TableCell />
        <TableCell />
        <TableCell />
        <TableCell>
          <VerifiedBadge
            verified={domain.humanVerified}
            onClick={
              onVerify
                ? () => handleVerify(domain.id, "domain", !domain.humanVerified)
                : undefined
            }
          />
        </TableCell>
        {hasEditPermission && (
          <TableCell>
            <ActionButtons
              onEdit={onEdit ? () => onEdit(domain, "domain") : undefined}
              onDelete={
                onDelete ? () => handleDelete(domain.id, "domain") : undefined
              }
            />
          </TableCell>
        )}
      </TableRow>,
    );

    if (!isExpanded) return;

    const sortedStrands = [...domain.strands].sort((a, b) => {
      if (sortField === "code") return compareField(a.code, b.code, sortDir);
      if (sortField === "name") return compareField(a.name, b.name, sortDir);
      return compareField(a.humanVerified, b.humanVerified, sortDir);
    });

    for (const strand of sortedStrands) {
      renderStrand(result, strand, searchQuery, verificationStatus);
    }

    // Render indicators directly under this domain (no strand)
    const sortedDomainIndicators = [...domain.indicators].sort((a, b) => {
      if (sortField === "code") return compareField(a.code, b.code, sortDir);
      if (sortField === "ageBand")
        return compareField(a.ageBand, b.ageBand, sortDir);
      if (sortField === "name")
        return compareField(
          a.title ?? a.description,
          b.title ?? b.description,
          sortDir,
        );
      return compareField(a.humanVerified, b.humanVerified, sortDir);
    });

    for (const indicator of sortedDomainIndicators) {
      if (
        !recordMatchesSearch(indicator, searchQuery ?? "") ||
        !matchesVerification(indicator.humanVerified, verificationStatus)
      )
        continue;
      renderIndicator(result, indicator, 2);
    }
  }

  function renderStrand(
    result: React.ReactNode[],
    strand: StrandWithChildren,
    searchQuery?: string,
    verificationStatus?: "all" | "verified" | "unverified",
  ) {
    if (!strandHasMatch(strand, searchQuery, verificationStatus)) return;

    const key = `strand-${strand.id}`;
    const isExpanded = expanded.has(key);

    result.push(
      <TableRow key={key} className="hover:bg-muted/40">
        <TableCell>
          <ExpandToggle
            expanded={isExpanded}
            onToggle={() => toggleExpand(key)}
            depth={2}
          />
        </TableCell>
        <TableCell>
          <span className="inline-flex items-center gap-2">
            <span className="text-xs font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
              {strand.code}
            </span>
            {strand.name}
          </span>
        </TableCell>
        <TableCell />
        <TableCell />
        <TableCell />
        <TableCell>
          <VerifiedBadge
            verified={strand.humanVerified}
            onClick={
              onVerify
                ? () => handleVerify(strand.id, "strand", !strand.humanVerified)
                : undefined
            }
          />
        </TableCell>
        {hasEditPermission && (
          <TableCell>
            <ActionButtons
              onEdit={onEdit ? () => onEdit(strand, "strand") : undefined}
              onDelete={
                onDelete ? () => handleDelete(strand.id, "strand") : undefined
              }
            />
          </TableCell>
        )}
      </TableRow>,
    );

    if (!isExpanded) return;

    const sortedSubStrands = [...strand.subStrands].sort((a, b) => {
      if (sortField === "code") return compareField(a.code, b.code, sortDir);
      if (sortField === "name") return compareField(a.name, b.name, sortDir);
      return compareField(a.humanVerified, b.humanVerified, sortDir);
    });

    for (const subStrand of sortedSubStrands) {
      renderSubStrand(
        result,
        subStrand,
        strand,
        searchQuery,
        verificationStatus,
      );
    }

    // Render indicators directly under this strand (no sub-strand)
    const sortedStrandIndicators = [...strand.indicators].sort((a, b) => {
      if (sortField === "code") return compareField(a.code, b.code, sortDir);
      if (sortField === "ageBand")
        return compareField(a.ageBand, b.ageBand, sortDir);
      if (sortField === "name")
        return compareField(
          a.title ?? a.description,
          b.title ?? b.description,
          sortDir,
        );
      return compareField(a.humanVerified, b.humanVerified, sortDir);
    });

    for (const indicator of sortedStrandIndicators) {
      if (
        !recordMatchesSearch(indicator, searchQuery ?? "") ||
        !matchesVerification(indicator.humanVerified, verificationStatus)
      )
        continue;
      renderIndicator(result, indicator, 3);
    }
  }

  function renderSubStrand(
    result: React.ReactNode[],
    subStrand: SubStrandWithChildren,
    strand: Strand,
    searchQuery?: string,
    verificationStatus?: "all" | "verified" | "unverified",
  ) {
    if (!subStrandHasMatch(subStrand, searchQuery, verificationStatus)) return;

    const key = `substrand-${subStrand.id}`;
    const isExpanded = expanded.has(key);

    result.push(
      <TableRow key={key} className="bg-muted/20 hover:bg-muted/40">
        <TableCell>
          <ExpandToggle
            expanded={isExpanded}
            onToggle={() => toggleExpand(key)}
            depth={3}
          />
        </TableCell>
        <TableCell>
          <span className="inline-flex items-center gap-2">
            <span className="text-xs font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
              {subStrand.code}
            </span>
            {subStrand.name}
          </span>
        </TableCell>
        <TableCell />
        <TableCell />
        <TableCell />
        <TableCell>
          <VerifiedBadge
            verified={subStrand.humanVerified}
            onClick={
              onVerify
                ? () =>
                    handleVerify(
                      subStrand.id,
                      "sub_strand",
                      !subStrand.humanVerified,
                    )
                : undefined
            }
          />
        </TableCell>
        {hasEditPermission && (
          <TableCell>
            <ActionButtons
              onEdit={
                onEdit ? () => onEdit(subStrand, "sub_strand") : undefined
              }
              onDelete={
                onDelete
                  ? () => handleDelete(subStrand.id, "sub_strand")
                  : undefined
              }
            />
          </TableCell>
        )}
      </TableRow>,
    );

    if (!isExpanded) return;

    const sortedIndicators = [...subStrand.indicators].sort((a, b) => {
      if (sortField === "code") return compareField(a.code, b.code, sortDir);
      if (sortField === "ageBand")
        return compareField(a.ageBand, b.ageBand, sortDir);
      if (sortField === "name")
        return compareField(
          a.title ?? a.description,
          b.title ?? b.description,
          sortDir,
        );
      return compareField(a.humanVerified, b.humanVerified, sortDir);
    });

    for (const indicator of sortedIndicators) {
      if (
        !recordMatchesSearch(indicator, searchQuery ?? "") ||
        !matchesVerification(indicator.humanVerified, verificationStatus)
      )
        continue;

      renderIndicator(result, indicator, 4, subStrand, strand);
    }
  }

  function renderIndicator(
    result: React.ReactNode[],
    indicator: Indicator,
    depth: number,
    subStrand?: SubStrand,
    strand?: Strand,
  ) {
    const key = `indicator-${indicator.id}`;

    let displayName = indicator.title ?? indicator.description;
    if (indicator.title && subStrand != null) {
      if (indicator.title == subStrand.name && indicator.description != null) {
        displayName = indicator.description;
      }
    } else if (
      indicator.title &&
      strand != null &&
      indicator.title == strand.name &&
      indicator.description != null
    ) {
      displayName = indicator.description;
    }

    result.push(
      <TableRow key={key} className="hover:bg-muted/30">
        <TableCell>
          <span style={{ paddingLeft: `${depth * 1.5}rem` }} />
        </TableCell>
        <TableCell colSpan={2}>
          <span className="inline-flex items-center gap-2">
            <span className="text-xs font-mono text-muted-foreground/70 bg-muted/50 px-1.5 py-0.5 rounded">
              {indicator.code}
            </span>
            <span className="text-sm text-foreground/80">{displayName}</span>
          </span>
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {indicator.ageBand}
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {indicator.sourcePage}
        </TableCell>
        <TableCell>
          <VerifiedBadge
            verified={indicator.humanVerified}
            onClick={
              onVerify
                ? () =>
                    handleVerify(
                      indicator.id,
                      "indicator",
                      !indicator.humanVerified,
                    )
                : undefined
            }
          />
        </TableCell>
        {hasEditPermission && (
          <TableCell>
            <ActionButtons
              onEdit={onEdit ? () => onEdit(indicator, "indicator") : undefined}
              onDelete={
                onDelete
                  ? () => handleDelete(indicator.id, "indicator")
                  : undefined
              }
            />
          </TableCell>
        )}
      </TableRow>,
    );
  }

  // ------ Render ------

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span className="text-sm">Loading hierarchy data…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={fetchDocuments}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <FilterBar
        filters={filters}
        onFilterChange={onFilterChange}
        countries={countries}
        states={states}
        expandButton={
          <Button
            variant="outline"
            size="sm"
            onClick={isAllExpanded ? handleCollapseAll : handleExpandAll}
            className="h-9"
          >
            {isAllExpanded ? (
              <>
                <ChevronsDownUp className="mr-2 h-4 w-4" />
                Collapse All
              </>
            ) : (
              <>
                <ChevronsUpDown className="mr-2 h-4 w-4" />
                Expand All
              </>
            )}
          </Button>
        }
      />

      <div className="rounded-lg border bg-card shadow-sm overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 hover:bg-muted/50">
              <TableHead className="w-[50px]" />
              <TableHead>
                <SortableHeader
                  label="Name"
                  field="name"
                  sortField={sortField}
                  sortDir={sortDir}
                  onSort={handleSort}
                />
              </TableHead>
              <TableHead className="w-[140px]">Details</TableHead>
              <TableHead className="w-[160px]">
                <SortableHeader
                  label="Age range (months)"
                  field="ageBand"
                  sortField={sortField}
                  sortDir={sortDir}
                  onSort={handleSort}
                />
              </TableHead>
              <TableHead className="w-[80px]">Page</TableHead>
              <TableHead className="w-[120px]">
                <SortableHeader
                  label="Status"
                  field="status"
                  sortField={sortField}
                  sortDir={sortDir}
                  onSort={handleSort}
                />
              </TableHead>
              {hasEditPermission && (
                <TableHead className="w-[100px]">Actions</TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length > 0 ? (
              rows
            ) : (
              <TableRow>
                <TableCell
                  colSpan={hasEditPermission ? 7 : 6}
                  className="text-center py-8 text-muted-foreground"
                >
                  No data found matching the current filters.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
