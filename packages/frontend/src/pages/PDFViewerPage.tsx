import { useParams, useSearchParams } from "react-router-dom";
import PDFViewer from "@/components/PDFViewer";

export default function PDFViewerPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();

  const documentId = Number(id);
  const page = searchParams.get("page");
  const initialPage = page ? Number(page) : undefined;

  if (!id || Number.isNaN(documentId)) {
    return <p className="text-destructive">Invalid document ID.</p>;
  }

  return <PDFViewer documentId={documentId} initialPage={initialPage} />;
}
