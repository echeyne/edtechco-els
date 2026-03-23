import { useState } from "react";
import { pdf } from "@react-pdf/renderer";
import { preparePdfData, PlanPdfDocument } from "@/components/PlanPdfDownload";
import type { PlanDetail } from "@/types";

interface PrintPlanButtonProps {
  plan: PlanDetail;
}

export default function PrintPlanButton({ plan }: PrintPlanButtonProps) {
  const [printing, setPrinting] = useState(false);

  const handlePrint = async () => {
    setPrinting(true);
    try {
      const data = preparePdfData(plan);
      const blob = await pdf(<PlanPdfDocument data={data} />).toBlob();
      const url = URL.createObjectURL(blob);
      const printWindow = window.open(url, "_blank");
      if (printWindow) {
        printWindow.addEventListener("load", () => {
          printWindow.print();
        });
      }
      // Clean up after a delay to allow the print dialog to open
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      console.error("Failed to generate print PDF:", err);
    } finally {
      setPrinting(false);
    }
  };

  return (
    <button
      onClick={handlePrint}
      disabled={printing}
      className="rounded-md border border-primary px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10 disabled:opacity-50"
      aria-label="Print plan"
    >
      {printing ? "Preparing…" : "Print"}
    </button>
  );
}
