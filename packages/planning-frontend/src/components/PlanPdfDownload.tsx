import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
  pdf,
} from "@react-pdf/renderer";
import type { PlanDetail } from "@/types";

/* ------------------------------------------------------------------ */
/*  PDF data preparation (exported for independent testing)            */
/* ------------------------------------------------------------------ */

export interface PdfActivityData {
  title: string;
  description: string;
  indicatorCode: string;
  indicatorDescription: string;
  domain: string;
  strand?: string;
  sectionLabel: string;
}

export interface PdfData {
  childName: string;
  childAge: string;
  state: string;
  duration: string;
  summary: string;
  activities: PdfActivityData[];
}

/**
 * Extracts all required fields from a PlanDetail into a flat structure
 * suitable for PDF rendering. Each activity carries its parent section label.
 */
export function preparePdfData(plan: PlanDetail): PdfData {
  const activities: PdfActivityData[] = [];

  for (const section of plan.content.sections) {
    for (const activity of section.activities) {
      activities.push({
        title: activity.title,
        description: activity.description,
        indicatorCode: activity.indicatorCode,
        indicatorDescription: activity.indicatorDescription,
        domain: activity.domain,
        strand: activity.strand,
        sectionLabel: section.label,
      });
    }
  }

  return {
    childName: plan.childName,
    childAge: plan.childAge,
    state: plan.state,
    duration: plan.duration,
    summary: plan.content.summary,
    activities,
  };
}

/* ------------------------------------------------------------------ */
/*  PDF styles                                                         */
/* ------------------------------------------------------------------ */

const styles = StyleSheet.create({
  page: {
    padding: 40,
    fontFamily: "Helvetica",
    fontSize: 11,
    color: "#1a1a1a",
  },
  header: {
    marginBottom: 20,
  },
  title: {
    fontSize: 20,
    fontFamily: "Helvetica-Bold",
    marginBottom: 6,
  },
  subtitle: {
    fontSize: 12,
    color: "#555",
  },
  summary: {
    fontSize: 11,
    color: "#444",
    fontStyle: "italic",
    marginBottom: 16,
  },
  sectionLabel: {
    fontSize: 14,
    fontFamily: "Helvetica-Bold",
    marginTop: 14,
    marginBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#ddd",
    paddingBottom: 4,
  },
  activityCard: {
    marginBottom: 10,
    padding: 10,
    borderWidth: 1,
    borderColor: "#e0e0e0",
    borderRadius: 4,
  },
  activityTitle: {
    fontSize: 12,
    fontFamily: "Helvetica-Bold",
    marginBottom: 4,
  },
  activityDescription: {
    fontSize: 10,
    color: "#333",
    marginBottom: 6,
  },
  standardRef: {
    fontSize: 9,
    color: "#555",
    backgroundColor: "#f5f5f5",
    padding: 6,
    borderRadius: 3,
  },
  standardCode: {
    fontFamily: "Helvetica-Bold",
    color: "#2563eb",
  },
  standardDomain: {
    color: "#666",
  },
  standardDescription: {
    marginTop: 2,
    color: "#444",
  },
});

/* ------------------------------------------------------------------ */
/*  PDF Document component                                             */
/* ------------------------------------------------------------------ */

export function PlanPdfDocument({ data }: { data: PdfData }) {
  // Group activities by section label to preserve structure
  const sections: { label: string; activities: PdfActivityData[] }[] = [];
  for (const activity of data.activities) {
    const last = sections[sections.length - 1];
    if (last && last.label === activity.sectionLabel) {
      last.activities.push(activity);
    } else {
      sections.push({ label: activity.sectionLabel, activities: [activity] });
    }
  }

  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <View style={styles.header}>
          <Text style={styles.title}>
            {data.childName}&apos;s Learning Plan
          </Text>
          <Text style={styles.subtitle}>
            {data.state} · Age {data.childAge} · {data.duration}
          </Text>
        </View>

        {data.summary ? (
          <Text style={styles.summary}>{data.summary}</Text>
        ) : null}

        {sections.map((section, si) => (
          <View key={si} wrap={false}>
            <Text style={styles.sectionLabel}>{section.label}</Text>
            {section.activities.map((act, ai) => (
              <View key={ai} style={styles.activityCard} wrap={false}>
                <Text style={styles.activityTitle}>{act.title}</Text>
                <Text style={styles.activityDescription}>
                  {act.description}
                </Text>
                <View style={styles.standardRef}>
                  <Text>
                    <Text style={styles.standardCode}>{act.indicatorCode}</Text>
                    <Text style={styles.standardDomain}> · {act.domain}</Text>
                    {act.strand ? (
                      <Text style={styles.standardDomain}> · {act.strand}</Text>
                    ) : null}
                  </Text>
                  <Text style={styles.standardDescription}>
                    {act.indicatorDescription}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        ))}
      </Page>
    </Document>
  );
}

/* ------------------------------------------------------------------ */
/*  Download button component                                          */
/* ------------------------------------------------------------------ */

interface PlanPdfDownloadProps {
  plan: PlanDetail;
}

export default function PlanPdfDownload({ plan }: PlanPdfDownloadProps) {
  const handleDownload = async () => {
    const data = preparePdfData(plan);
    const blob = await pdf(<PlanPdfDocument data={data} />).toBlob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${plan.childName}-learning-plan.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <button
      onClick={handleDownload}
      className="rounded-md border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
      aria-label="Download plan as PDF"
    >
      Download PDF
    </button>
  );
}
