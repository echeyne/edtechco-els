import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import type { PlanSummary } from "@/types";

/* ------------------------------------------------------------------ */
/*  PlanCard                                                           */
/* ------------------------------------------------------------------ */

function PlanCard({ plan }: { plan: PlanSummary }) {
  const formattedDate = new Date(plan.createdAt).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <Link
      to={`/planning/${plan.id}`}
      className="block rounded-lg border bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
      data-testid="plan-card"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            {plan.childName}&apos;s Plan
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {plan.state} · Age {plan.childAge} · {plan.duration}
          </p>
        </div>
        <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
          {plan.status}
        </span>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{formattedDate}</p>
    </Link>
  );
}

/* ------------------------------------------------------------------ */
/*  EmptyState                                                         */
/* ------------------------------------------------------------------ */

function EmptyState({ onStartNew }: { onStartNew?: () => void }) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center"
      data-testid="empty-state"
    >
      <p className="text-sm text-muted-foreground">
        You don&apos;t have any plans yet.
      </p>
      <button
        onClick={onStartNew}
        className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        Start a new plan
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  PlanList                                                           */
/* ------------------------------------------------------------------ */

export interface PlanListProps {
  onStartNew?: () => void;
  refreshKey?: number;
}

export default function PlanList({ onStartNew, refreshKey }: PlanListProps) {
  const { token } = useAuth();
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPlans = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/plans", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Failed to load plans (${res.status})`);
      const data: PlanSummary[] = await res.json();
      setPlans(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load plans");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans, refreshKey]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading plans…</p>;
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive"
      >
        {error}
      </div>
    );
  }

  if (plans.length === 0) {
    return <EmptyState onStartNew={onStartNew} />;
  }

  return (
    <div className="space-y-3" data-testid="plan-list">
      {plans.map((plan) => (
        <PlanCard key={plan.id} plan={plan} />
      ))}
    </div>
  );
}

export { PlanCard, EmptyState };
