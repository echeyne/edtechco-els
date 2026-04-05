import { useState, useCallback, useEffect } from "react";
import { useLocation } from "react-router-dom";
import ChatPanel from "@/components/ChatPanel";
import PlanList from "@/components/PlanList";

interface RefineState {
  refinePlanId?: string;
  initialMessage?: string;
}

export default function PlanningPage() {
  const location = useLocation();
  const [view, setView] = useState<"list" | "chat">("list");
  const [refreshKey, setRefreshKey] = useState(0);
  const [refinePlanId, setRefinePlanId] = useState<string | undefined>();
  const [initialMessage, setInitialMessage] = useState<string | undefined>();

  // If navigated here with refine state, open chat with that context
  useEffect(() => {
    const state = location.state as RefineState | null;
    if (state?.refinePlanId) {
      setRefinePlanId(state.refinePlanId);
      setInitialMessage(state.initialMessage);
      setView("chat");
      // Clear the navigation state so refreshing doesn't re-trigger
      window.history.replaceState({}, "");
    }
  }, [location.state]);

  const handleStartNew = useCallback(() => {
    setRefinePlanId(undefined);
    setInitialMessage(undefined);
    setView("chat");
  }, []);

  const handlePlanEvent = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  const handleBackToList = useCallback(() => {
    setRefinePlanId(undefined);
    setInitialMessage(undefined);
    setView("list");
    setRefreshKey((k) => k + 1);
  }, []);

  return (
    <div
      className={`max-w-4xl mx-auto w-full flex-1 flex flex-col ${view === "chat" ? "min-h-0 overflow-hidden" : ""}`}
    >
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <h2 className="text-xl font-semibold">My Plans</h2>
        {view === "list" ? (
          <button
            onClick={handleStartNew}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            New Plan
          </button>
        ) : (
          <button
            onClick={handleBackToList}
            className="rounded-md border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
          >
            ← Back to Plans
          </button>
        )}
      </div>

      {view === "list" ? (
        <PlanList onStartNew={handleStartNew} refreshKey={refreshKey} />
      ) : (
        <div className="flex-1 min-h-0 pb-6">
          <ChatPanel
            planId={refinePlanId}
            initialMessage={initialMessage}
            onPlanEvent={handlePlanEvent}
          />
        </div>
      )}
    </div>
  );
}
