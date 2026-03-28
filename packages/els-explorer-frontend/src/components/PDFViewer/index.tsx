import { useState, useEffect, useCallback } from "react";
import { getPdfUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  Loader2,
  RefreshCw,
} from "lucide-react";

export interface PDFViewerProps {
  documentId: number;
  initialPage?: number;
}

export default function PDFViewer({ documentId, initialPage }: PDFViewerProps) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [currentPage, setCurrentPage] = useState(initialPage ?? 1);
  const [pageInput, setPageInput] = useState(String(initialPage ?? 1));

  const fetchUrl = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSourceUrl(null);
    setExpired(false);

    try {
      const data = await getPdfUrl(documentId);
      setPdfUrl(data.url);
      setExpiresAt(data.expiresAt);
    } catch (err: unknown) {
      const apiErr = err as Error & { sourceUrl?: string };
      setError(apiErr.message ?? "Failed to load PDF");
      if (apiErr.sourceUrl) {
        setSourceUrl(apiErr.sourceUrl);
      }
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    fetchUrl();
  }, [fetchUrl]);

  // Check expiration periodically
  useEffect(() => {
    if (!expiresAt) return;

    const check = () => {
      if (new Date(expiresAt) <= new Date()) {
        setExpired(true);
      }
    };

    check();
    const interval = setInterval(check, 30_000);
    return () => clearInterval(interval);
  }, [expiresAt]);

  const iframeSrc = pdfUrl ? `${pdfUrl}#page=${currentPage}` : undefined;

  const goToPage = (page: number) => {
    const p = Math.max(1, page);
    setCurrentPage(p);
    setPageInput(String(p));
  };

  const handlePageInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      const parsed = parseInt(pageInput, 10);
      if (!isNaN(parsed) && parsed >= 1) {
        goToPage(parsed);
      } else {
        setPageInput(String(currentPage));
      }
    }
  };

  const handlePageInputBlur = () => {
    const parsed = parseInt(pageInput, 10);
    if (!isNaN(parsed) && parsed >= 1) {
      goToPage(parsed);
    } else {
      setPageInput(String(currentPage));
    }
  };

  // ---- Loading state ----
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-16 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin" />
        <span>Loading PDF…</span>
      </div>
    );
  }

  // ---- Error state ----
  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-16">
        <p className="text-destructive">{error}</p>
        {sourceUrl ? (
          <div className="flex flex-col items-center gap-2 text-center">
            <p className="text-sm text-muted-foreground">
              The original document is available at its source website:
            </p>
            <Button variant="outline" asChild>
              <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" />
                View original source
              </a>
            </Button>
          </div>
        ) : (
          <Button variant="outline" onClick={fetchUrl}>
            Retry
          </Button>
        )}
      </div>
    );
  }

  // ---- Expired state ----
  if (expired) {
    return (
      <div className="flex flex-col items-center gap-4 py-16">
        <p className="text-muted-foreground">The PDF link has expired.</p>
        <Button variant="outline" onClick={fetchUrl}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh link
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* PDF iframe */}
      <iframe
        key={iframeSrc}
        src={iframeSrc}
        className="flex-1 w-full min-h-[600px] border-0"
        title="PDF Document Viewer"
      />
    </div>
  );
}
