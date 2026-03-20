import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { getPlan, deletePlan, ApiError } from "@/lib/api";
import PlanDisplay from "@/components/PlanDisplay";
import ChatPanel from "@/components/ChatPanel";
import type { PlanDetail } from "@/types";

export default function PlanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { token } = useAuth();

  const [plan, setPlan] = useState<PlanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const fetchPlan = useCallback(async () => {
    if (!token || !id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getPlan(id, token);
      setPlan(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("Plan not found");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load plan");
    } finally {
      setLoading(false);
    }
  }, [token, id]);

  useEffect(() => {
    fetchPlan();
  }, [fetchPlan]);

  const handleDelete = useCallback(async () => {
    if (!token || !id || deleting) return;
    const confirmed = window.confirm(
      "Are you sure you want to delete this plan?",
    );
    if (!confirmed) return;
    setDeleting(true);
    try {
      await deletePlan(id, token);
      navigate("/planning");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete plan");
      setDeleting(false);
    }
  }, [token, id, deleting, navigate]);

  const handlePlanEvent = useCallback(() => {
    // Re-fetch plan when it's updated via chat refinement
    fetchPlan();
  }, [fetchPlan]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading plan…</p>;
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto">
        <div
          role="alert"
          className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error}
        </div>
        <button
          onClick={() => navigate("/planning")}
          className="mt-4 rounded-md border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
        >
          ← Back to Plans
        </button>
      </div>
    );
  }

  if (!plan) return null;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate("/planning")}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Back to Plans
        </button>
      </div>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold">
            {plan.childName}&apos;s Plan
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {plan.state} · Age {plan.childAge} · {plan.duration}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowChat((v) => !v)}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            {showChat ? "Hide Chat" : "Refine this plan"}
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="rounded-md border border-destructive px-4 py-2 text-sm font-medium text-destructive hover:bg-destructive/10 disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>

      {showChat && (
        <div className="mb-6 h-[400px]">
          <ChatPanel planId={plan.id} onPlanEvent={handlePlanEvent} />
        </div>
      )}

      <PlanDisplay content={plan.content} />
    </div>
  );
}
