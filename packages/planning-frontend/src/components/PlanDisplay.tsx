import type { PlanContent, PlanActivity } from "@/types";

/* ------------------------------------------------------------------ */
/*  StandardReference                                                  */
/* ------------------------------------------------------------------ */

function StandardReference({
  indicatorCode,
  indicatorDescription,
  domain,
  strand,
}: Pick<
  PlanActivity,
  "indicatorCode" | "indicatorDescription" | "domain" | "strand"
>) {
  return (
    <div className="mt-2 rounded border border-primary/20 bg-primary/5 px-3 py-2 text-xs">
      <span className="font-semibold text-primary">{indicatorCode}</span>
      <span className="mx-1 text-muted-foreground">·</span>
      <span className="text-muted-foreground">{domain}</span>
      {strand && (
        <>
          <span className="mx-1 text-muted-foreground">·</span>
          <span className="text-muted-foreground">{strand}</span>
        </>
      )}
      <p className="mt-1 text-foreground">{indicatorDescription}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ActivityCard                                                       */
/* ------------------------------------------------------------------ */

function ActivityCard({ activity }: { activity: PlanActivity }) {
  return (
    <div
      className="rounded-lg border bg-white p-4 shadow-sm"
      data-testid="activity-card"
    >
      <h4 className="text-sm font-semibold text-foreground">
        {activity.title}
      </h4>
      <p className="mt-1 text-sm text-muted-foreground">
        {activity.description}
      </p>
      <StandardReference
        indicatorCode={activity.indicatorCode}
        indicatorDescription={activity.indicatorDescription}
        domain={activity.domain}
        strand={activity.strand}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ActivitySection                                                    */
/* ------------------------------------------------------------------ */

function ActivitySection({
  label,
  description,
  activities,
}: {
  label: string;
  description?: string;
  activities: PlanActivity[];
}) {
  return (
    <section className="mb-6" data-testid="activity-section">
      <h3 className="text-lg font-semibold text-foreground">{label}</h3>
      {description && (
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      )}
      <div className="mt-3 space-y-3">
        {activities.map((activity, i) => (
          <ActivityCard key={i} activity={activity} />
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  PlanDisplay                                                        */
/* ------------------------------------------------------------------ */

export interface PlanDisplayProps {
  content: PlanContent;
}

export default function PlanDisplay({ content }: PlanDisplayProps) {
  return (
    <div className="space-y-6">
      {content.summary && (
        <p className="text-sm text-muted-foreground italic">
          {content.summary}
        </p>
      )}
      {content.sections.map((section, i) => (
        <ActivitySection
          key={i}
          label={section.label}
          description={section.description}
          activities={section.activities}
        />
      ))}
    </div>
  );
}

export { ActivitySection, ActivityCard, StandardReference };
