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
  ShieldCheck,
  Search,
  Edit,
  Trash2,
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
  onDelete?: (id: number, type: string) => void;
  onVerify?: (id: number, type: string, verified: boolean) => Promise<void>;
  onDataLoaded?: (documents: Document[], hierarchies: Map<number, HierarchyResponse>) => void;
}

type SortField = "code" | "name" | "status";
type SortDir = "asc" | "desc";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function matchesSearch(text: string, query: string): boolean {
  return text.toLowerCase().includes(query.toLowerCase());
}

function recordMatchesSearch(
  record: { code?: string; name?: string; title?: string | null; description?: string | null },
  query: string,
): boolean {
  if (!query) return true;
  const fields = [record.code, record.name, record.title, record.description].filter(
    Boolean,
  ) as string[];
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
    <Badge className="bg-green-100 text-green-800 border-green-200 hover:bg-green-100">
      <ShieldCheck className="mr-1 h-3 w-3" />
      Verified
    </Badge>
  ) : (
    <Badge variant="secondary" className="text-muted-foreground">
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
}: {
  filters: FilterState;
  onFilterChange: (f: FilterState) => void;
  countries: string[];
  states: string[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 mb-4">
      {/* Search */}
      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search..."
          value={filters.searchQuery ?? ""}
          onChange={(e) =>
            onFilterChange({ ...filters, searchQuery: e.target.value })
          }
          className="pl-9"
        />
      </div>

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
        <SelectTrigger className="w-[160px]">
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
        <SelectTrigger className="w-[160px]">
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
        <SelectTrigger className="w-[160px]">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Status</SelectItem>
          <SelectItem value="verified">Verified</SelectItem>
          <SelectItem value="unverified">Unverified</SelectItem>
        </SelectContent>
      </Select>
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
      className="inline-flex items-center gap-1 hover:text-foreground"
      onClick={() => onSort(field)}
    >
      {label}
      {active && <span className="text-xs">{sortDir === "asc" ? "↑" : "↓"}</span>}
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
}: HierarchyTableProps) {
  const { hasEditPermission } = useAuth();

  // Data state
  const [documents, setDocuments] = useState<Document[]>([]);
  const [hierarchies, setHierarchies] = useState<Map<number, HierarchyResponse>>(
    new Map(),
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

  // ------ Expand / collapse ------

  const toggleExpand = useCallback((key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

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
        <TableRow key={docKey} className="bg-muted/30 font-medium">
          <TableCell>
            <ExpandToggle
              expanded={docExpanded}
              onToggle={() => toggleExpand(docKey)}
              depth={0}
            />
          </TableCell>
          <TableCell className="font-semibold">{doc.title}</TableCell>
          <TableCell>
            {doc.country} / {doc.state}
          </TableCell>
          <TableCell>{doc.versionYear}</TableCell>
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
    onDelete,
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
      <TableRow key={key} className="bg-blue-50/50">
        <TableCell>
          <ExpandToggle
            expanded={isExpanded}
            onToggle={() => toggleExpand(key)}
            depth={1}
          />
        </TableCell>
        <TableCell>
          <span className="text-xs text-muted-foreground mr-2">{domain.code}</span>
          {domain.name}
        </TableCell>
        <TableCell />
        <TableCell />
        <TableCell>
          <VerifiedBadge
            verified={domain.humanVerified}
            onClick={onVerify ? () => onVerify(domain.id, "domain", !domain.humanVerified) : undefined}
          />
        </TableCell>
        {hasEditPermission && (
          <TableCell>
            <ActionButtons
              onEdit={onEdit ? () => onEdit(domain, "domain") : undefined}
              onDelete={onDelete ? () => onDelete(domain.id, "domain") : undefined}
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
      <TableRow key={key}>
        <TableCell>
          <ExpandToggle
            expanded={isExpanded}
            onToggle={() => toggleExpand(key)}
            depth={2}
          />
        </TableCell>
        <TableCell>
          <span className="text-xs text-muted-foreground mr-2">{strand.code}</span>
          {strand.name}
        </TableCell>
        <TableCell />
        <TableCell />
        <TableCell>
          <VerifiedBadge
            verified={strand.humanVerified}
            onClick={onVerify ? () => onVerify(strand.id, "strand", !strand.humanVerified) : undefined}
          />
        </TableCell>
        {hasEditPermission && (
          <TableCell>
            <ActionButtons
              onEdit={onEdit ? () => onEdit(strand, "strand") : undefined}
              onDelete={onDelete ? () => onDelete(strand.id, "strand") : undefined}
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
      renderSubStrand(result, subStrand, searchQuery, verificationStatus);
    }
  }

  function renderSubStrand(
    result: React.ReactNode[],
    subStrand: SubStrandWithChildren,
    searchQuery?: string,
    verificationStatus?: "all" | "verified" | "unverified",
  ) {
    if (!subStrandHasMatch(subStrand, searchQuery, verificationStatus)) return;

    const key = `substrand-${subStrand.id}`;
    const isExpanded = expanded.has(key);

    result.push(
      <TableRow key={key} className="bg-muted/20">
        <TableCell>
          <ExpandToggle
            expanded={isExpanded}
            onToggle={() => toggleExpand(key)}
            depth={3}
          />
        </TableCell>
        <TableCell>
          <span className="text-xs text-muted-foreground mr-2">{subStrand.code}</span>
          {subStrand.name}
        </TableCell>
        <TableCell />
        <TableCell />
        <TableCell>
          <VerifiedBadge
            verified={subStrand.humanVerified}
            onClick={onVerify ? () => onVerify(subStrand.id, "sub_strand", !subStrand.humanVerified) : undefined}
          />
        </TableCell>
        {hasEditPermission && (
          <TableCell>
            <ActionButtons
              onEdit={onEdit ? () => onEdit(subStrand, "sub_strand") : undefined}
              onDelete={
                onDelete ? () => onDelete(subStrand.id, "sub_strand") : undefined
              }
            />
          </TableCell>
        )}
      </TableRow>,
    );

    if (!isExpanded) return;

    const sortedIndicators = [...subStrand.indicators].sort((a, b) => {
      if (sortField === "code") return compareField(a.code, b.code, sortDir);
      if (sortField === "name")
        return compareField(a.title ?? a.description, b.title ?? b.description, sortDir);
      return compareField(a.humanVerified, b.humanVerified, sortDir);
    });

    for (const indicator of sortedIndicators) {
      if (
        !recordMatchesSearch(indicator, searchQuery ?? "") ||
        !matchesVerification(indicator.humanVerified, verificationStatus)
      )
        continue;

      renderIndicator(result, indicator);
    }
  }

  function renderIndicator(result: React.ReactNode[], indicator: Indicator) {
    const key = `indicator-${indicator.id}`;

    result.push(
      <TableRow key={key}>
        <TableCell>
          <span style={{ paddingLeft: "6rem" }} />
        </TableCell>
        <TableCell>
          <span className="text-xs text-muted-foreground mr-2">
            {indicator.code}
          </span>
          <span className="text-sm">
            {indicator.title ?? indicator.description}
          </span>
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {indicator.ageBand}
        </TableCell>
        <TableCell />
        <TableCell>
          <VerifiedBadge
            verified={indicator.humanVerified}
            onClick={onVerify ? () => onVerify(indicator.id, "indicator", !indicator.humanVerified) : undefined}
          />
        </TableCell>
        {hasEditPermission && (
          <TableCell>
            <ActionButtons
              onEdit={onEdit ? () => onEdit(indicator, "indicator") : undefined}
              onDelete={
                onDelete ? () => onDelete(indicator.id, "indicator") : undefined
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
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        Loading hierarchy data…
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
      />

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
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
              <TableHead className="w-[80px]">
                <SortableHeader
                  label="Code"
                  field="code"
                  sortField={sortField}
                  sortDir={sortDir}
                  onSort={handleSort}
                />
              </TableHead>
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
                  colSpan={hasEditPermission ? 6 : 5}
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
