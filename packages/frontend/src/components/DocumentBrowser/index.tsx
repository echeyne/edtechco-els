import { useState, useEffect, useMemo } from "react";
import type { Document } from "@els/shared";
import { getDocuments } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  FileText,
  Search,
  ChevronRight,
  Globe,
  MapPin,
  Calendar,
} from "lucide-react";
import { Link } from "react-router-dom";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DocumentBrowserProps {
  onDocumentSelect?: (documentId: number) => void;
}

interface DocumentListItem {
  id: number;
  title: string;
  country: string;
  state: string;
  versionYear: number;
  s3Key: string;
}

/** Group key: country → state → documents */
interface StateGroup {
  state: string;
  documents: DocumentListItem[];
}

interface CountryGroup {
  country: string;
  states: StateGroup[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toListItem(doc: Document): DocumentListItem {
  return {
    id: doc.id,
    title: doc.title,
    country: doc.country,
    state: doc.state,
    versionYear: doc.versionYear,
    s3Key: doc.sourceUrl ?? "",
  };
}

function groupByCountryState(items: DocumentListItem[]): CountryGroup[] {
  const countryMap = new Map<string, Map<string, DocumentListItem[]>>();

  for (const item of items) {
    if (!countryMap.has(item.country)) {
      countryMap.set(item.country, new Map());
    }
    const stateMap = countryMap.get(item.country)!;
    if (!stateMap.has(item.state)) {
      stateMap.set(item.state, []);
    }
    stateMap.get(item.state)!.push(item);
  }

  const groups: CountryGroup[] = [];
  for (const [country, stateMap] of [...countryMap.entries()].sort((a, b) =>
    a[0].localeCompare(b[0]),
  )) {
    const states: StateGroup[] = [];
    for (const [state, docs] of [...stateMap.entries()].sort((a, b) =>
      a[0].localeCompare(b[0]),
    )) {
      states.push({
        state,
        documents: docs.sort((a, b) => b.versionYear - a.versionYear),
      });
    }
    groups.push({ country, states });
  }

  return groups;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DocumentBrowser({
  onDocumentSelect,
}: DocumentBrowserProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getDocuments()
      .then((docs) => {
        if (!cancelled) {
          setDocuments(docs.map(toListItem));
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load documents");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return documents;
    const q = searchQuery.toLowerCase();
    return documents.filter((d) => d.title.toLowerCase().includes(q));
  }, [documents, searchQuery]);

  const groups = useMemo(() => groupByCountryState(filtered), [filtered]);

  // ---- Loading state ----
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        Loading documents…
      </div>
    );
  }

  // ---- Error state ----
  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-16">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search documents by title…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Empty state */}
      {groups.length === 0 && (
        <p className="py-8 text-center text-muted-foreground">
          {searchQuery ? "No documents match your search." : "No documents available."}
        </p>
      )}

      {/* Grouped list */}
      {groups.map((countryGroup) => (
        <section key={countryGroup.country} className="space-y-4">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Globe className="h-5 w-5 text-muted-foreground" />
            {countryGroup.country}
          </h2>

          {countryGroup.states.map((stateGroup) => (
            <div key={stateGroup.state} className="ml-4 space-y-2">
              <h3 className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <MapPin className="h-4 w-4" />
                {stateGroup.state}
              </h3>

              <ul className="ml-4 space-y-1">
                {stateGroup.documents.map((doc) => (
                  <li key={doc.id}>
                    <Link
                      to={`/documents/${doc.id}/view`}
                      onClick={() => onDocumentSelect?.(doc.id)}
                      className={cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm",
                        "hover:bg-accent transition-colors",
                      )}
                    >
                      <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="flex-1 truncate">{doc.title}</span>
                      <Badge variant="secondary" className="shrink-0">
                        <Calendar className="mr-1 h-3 w-3" />
                        {doc.versionYear}
                      </Badge>
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
