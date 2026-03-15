import { useState, useEffect, useCallback } from "react";
import { getPdfUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  ChevronLeft,
  ChevronRight,
  Download,
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
  const [expired, setExpired] = useState(false);
  const [currentPage, setCurrentPage] = useState(initialPage ?? 1);
  const [pageInput, setPageInput] = useState(String(initialPage ?? 1));

  const fetchUrl = useCallback(async () => {
    setLoading(true);
    setError(null);
    setExpired(false);

    try {
      const data = await getPdfUrl(documentId);
      setPdfUrl(data.url);
      setExpiresAt(data.expiresAt);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load PDF");
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

  const iframeSrc = pdfUrl
    ? `${pdfUrl}#page=${currentPage}`
    : undefined;

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
        <Button variant="outline" onClick={fetchUrl}>
          Retry
        </Button>
      </div>
    );
  }

  // ---- Expired state ----
  if (expired) {
    return (
      <div className="flex flex-col items-center gap-4 py-16">
        <p className="text-muted-foreground">
          The PDF link has expired.
        </p>
        <Button variant="outline" onClick={fetchUrl}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh link
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div
        className={cn(
          "flex items-center gap-2 border-b bg-muted/50 px-4 py-2",
        )}
      >
        {/* Page navigation */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => goToPage(currentPage - 1)}
          disabled={currentPage <= 1}
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>

        <div className="flex items-center gap-1 text-sm">
          <span>Page</span>
          <Input
            className="h-8 w-16 text-center"
            value={pageInput}
            onChange={(e) => setPageInput(e.target.value)}
            onKeyDown={handlePageInputKeyDown}
            onBlur={handlePageInputBlur}
            aria-label="Page number"
          />
        </div>

        <Button
          variant="outline"
          size="icon"
          onClick={() => goToPage(currentPage + 1)}
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>

        <div className="flex-1" />

        {/* Download */}
        <Button
          variant="outline"
          size="sm"
          asChild
        >
          <a href={pdfUrl ?? "#"} target="_blank" rel="noopener noreferrer">
            <Download className="mr-2 h-4 w-4" />
            Download
          </a>
        </Button>
      </div>

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
