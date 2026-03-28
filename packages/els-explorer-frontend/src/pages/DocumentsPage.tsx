import DocumentBrowser from "@/components/DocumentBrowser";

export default function DocumentsPage() {
  return (
    <div>
      <h2 className="mb-2 text-xl font-semibold">Source Documents</h2>
      <p className="mb-6 text-sm text-muted-foreground">
        Each document listed below includes the publishing agency and a link to
        the original source. For the full, unedited document and any related
        materials, please follow the source link provided with each entry.
      </p>
      <DocumentBrowser />
    </div>
  );
}
