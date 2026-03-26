import DocumentBrowser from "@/components/DocumentBrowser";

export default function DocumentsPage() {
  return (
    <div>
      <h2 className="mb-4 text-xl font-semibold">Source Documents</h2>
      <p className="mb-4">
        For processing; parts of the document not related to standards were
        removed. To see the full, unedited documents, please visit the linked
        website.
      </p>
      <DocumentBrowser />
    </div>
  );
}
