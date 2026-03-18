import { useState, useCallback, useRef } from "react";
import type { Document, Domain, Strand, SubStrand, Indicator, HierarchyResponse } from "@els/shared";
import {
  HierarchyTable,
  type FilterState,
} from "@/components/HierarchyTable";
import { EditModal } from "@/components/EditModal";
import { useAuth } from "@/contexts/AuthContext";
import {
  deleteDomain,
  deleteStrand,
  deleteSubStrand,
  deleteIndicator,
  verifyDomain,
  verifyStrand,
  verifySubStrand,
  verifyIndicator,
} from "@/lib/api";

type RecordType = "domain" | "strand" | "sub_strand" | "indicator";

const DELETE_FN: Record<
  RecordType,
  (id: number, token: string) => Promise<{ success: boolean }>
> = {
  domain: deleteDomain,
  strand: deleteStrand,
  sub_strand: deleteSubStrand,
  indicator: deleteIndicator,
};

const VERIFY_FN: Record<
  RecordType,
  (id: number, data: { humanVerified: boolean }, token: string) => Promise<unknown>
> = {
  domain: verifyDomain,
  strand: verifyStrand,
  sub_strand: verifySubStrand,
  indicator: verifyIndicator,
};

export default function HomePage() {
  const { hasEditPermission, token } = useAuth();

  const [filters, setFilters] = useState<FilterState>({});

  // Edit modal state
  const [editRecord, setEditRecord] = useState<
    (Domain | Strand | SubStrand | Indicator) | null
  >(null);
  const [editType, setEditType] = useState<RecordType>("domain");
  const [editOpen, setEditOpen] = useState(false);

  // Data from HierarchyTable for parent selectors in EditModal
  const docsRef = useRef<Document[]>([]);
  const hierarchiesRef = useRef<Map<number, HierarchyResponse>>(new Map());

  // Refresh key – bump to force HierarchyTable to re-fetch
  const [refreshKey, setRefreshKey] = useState(0);

  const handleDataLoaded = useCallback(
    (docs: Document[], hierarchies: Map<number, HierarchyResponse>) => {
      docsRef.current = docs;
      hierarchiesRef.current = hierarchies;
    },
    [],
  );

  const handleEdit = useCallback(
    (record: Domain | Strand | SubStrand | Indicator, type: string) => {
      setEditRecord(record);
      setEditType(type as RecordType);
      setEditOpen(true);
    },
    [],
  );

  const handleDelete = useCallback(
    async (id: number, type: string) => {
      if (!token) return;
      const confirmed = window.confirm(
        `Are you sure you want to delete this ${type.replace("_", " ")}?`,
      );
      if (!confirmed) return;

      const fn = DELETE_FN[type as RecordType];
      if (!fn) return;

      await fn(id, token);
      setRefreshKey((k) => k + 1);
    },
    [token],
  );

  const handleVerify = useCallback(
    async (id: number, type: string, verified: boolean) => {
      if (!token) return;
      const fn = VERIFY_FN[type as RecordType];
      if (!fn) return;
      await fn(id, { humanVerified: verified }, token);
      setRefreshKey((k) => k + 1);
    },
    [token],
  );

  const handleSave = useCallback(
    (_updated: Domain | Strand | SubStrand | Indicator) => {
      setRefreshKey((k) => k + 1);
    },
    [],
  );

  return (
    <div>
      <HierarchyTable
        key={refreshKey}
        filters={filters}
        onFilterChange={setFilters}
        onEdit={hasEditPermission ? handleEdit : undefined}
        onDelete={hasEditPermission ? handleDelete : undefined}
        onVerify={hasEditPermission ? handleVerify : undefined}
        onDataLoaded={handleDataLoaded}
      />

      {editRecord && (
        <EditModal
          open={editOpen}
          onOpenChange={setEditOpen}
          record={editRecord}
          recordType={editType}
          onSave={handleSave}
          documents={docsRef.current}
          hierarchies={hierarchiesRef.current}
        />
      )}
    </div>
  );
}
