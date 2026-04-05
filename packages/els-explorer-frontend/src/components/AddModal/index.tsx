import { useState, useCallback, useMemo } from "react";
import type {
  Document,
  Domain,
  Strand,
  SubStrand,
  Indicator,
  HierarchyResponse,
} from "@els/shared";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  createDomain,
  createStrand,
  createSubStrand,
  createIndicator,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

type RecordType = "domain" | "strand" | "sub_strand" | "indicator";

export interface AddModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (
    record: Domain | Strand | SubStrand | Indicator,
    type: RecordType,
  ) => void;
  documents?: Document[];
  hierarchies?: Map<number, HierarchyResponse>;
}

const RECORD_TYPE_LABELS: Record<RecordType, string> = {
  domain: "Domain",
  strand: "Strand",
  sub_strand: "Sub-Strand",
  indicator: "Indicator",
};

export function AddModal({
  open,
  onOpenChange,
  onCreated,
  documents,
  hierarchies,
}: AddModalProps) {
  const { token } = useAuth();

  // What type of record to create
  const [recordType, setRecordType] = useState<RecordType>("indicator");

  // Form state
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [ageBand, setAgeBand] = useState("");
  const [sourcePage, setSourcePage] = useState("");
  const [sourceText, setSourceText] = useState("");

  // Parent ID state
  const [parentDocumentId, setParentDocumentId] = useState<number | null>(null);
  const [parentDomainId, setParentDomainId] = useState<number | null>(null);
  const [parentStrandId, setParentStrandId] = useState<number | null>(null);
  const [parentSubStrandId, setParentSubStrandId] = useState<number | null>(
    null,
  );

  // For indicators: whether it's parented under a sub-strand or directly under a strand/domain
  const [indicatorParentLevel, setIndicatorParentLevel] = useState<
    "sub_strand" | "strand" | "domain"
  >("sub_strand");

  // UI state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when modal opens/closes or record type changes
  const resetForm = useCallback(() => {
    setCode("");
    setName("");
    setTitle("");
    setDescription("");
    setAgeBand("");
    setSourcePage("");
    setSourceText("");
    setParentDocumentId(null);
    setParentDomainId(null);
    setParentStrandId(null);
    setParentSubStrandId(null);
    setIndicatorParentLevel("sub_strand");
    setError(null);
  }, []);

  const handleOpenChange = useCallback(
    (isOpen: boolean) => {
      if (!isOpen) resetForm();
      onOpenChange(isOpen);
    },
    [onOpenChange, resetForm],
  );

  const handleRecordTypeChange = useCallback(
    (type: RecordType) => {
      resetForm();
      setRecordType(type);
    },
    [resetForm],
  );

  // Build parent option lists from hierarchies
  const allDomains = useMemo(() => {
    if (!hierarchies) return [];
    const result: { id: number; label: string; documentId: number }[] = [];
    for (const [, h] of hierarchies) {
      for (const d of h.domains) {
        result.push({
          id: d.id,
          label: `${d.code} — ${d.name}`,
          documentId: h.document.id,
        });
      }
    }
    return result;
  }, [hierarchies]);

  const allStrands = useMemo(() => {
    if (!hierarchies) return [];
    const result: { id: number; label: string; domainId: number }[] = [];
    for (const [, h] of hierarchies) {
      for (const d of h.domains) {
        for (const s of d.strands) {
          result.push({
            id: s.id,
            label: `${s.code} — ${s.name}`,
            domainId: d.id,
          });
        }
      }
    }
    return result;
  }, [hierarchies]);

  const allSubStrands = useMemo(() => {
    if (!hierarchies) return [];
    const result: { id: number; label: string; strandId: number }[] = [];
    for (const [, h] of hierarchies) {
      for (const d of h.domains) {
        for (const s of d.strands) {
          for (const ss of s.subStrands) {
            result.push({
              id: ss.id,
              label: `${ss.code} — ${ss.name}`,
              strandId: s.id,
            });
          }
        }
      }
    }
    return result;
  }, [hierarchies]);

  // Resolve the domainId for an indicator based on its parent chain
  const resolvedDomainId = useMemo(() => {
    if (indicatorParentLevel === "domain") return parentDomainId;
    if (indicatorParentLevel === "strand" && parentStrandId) {
      const strand = allStrands.find((s) => s.id === parentStrandId);
      return strand?.domainId ?? null;
    }
    if (indicatorParentLevel === "sub_strand" && parentSubStrandId) {
      const ss = allSubStrands.find((s) => s.id === parentSubStrandId);
      if (ss) {
        const strand = allStrands.find((s) => s.id === ss.strandId);
        return strand?.domainId ?? null;
      }
    }
    return null;
  }, [
    indicatorParentLevel,
    parentDomainId,
    parentStrandId,
    parentSubStrandId,
    allStrands,
    allSubStrands,
  ]);

  const handleSave = useCallback(async () => {
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      let created: Domain | Strand | SubStrand | Indicator;

      if (recordType === "domain") {
        if (!parentDocumentId) {
          setError("Please select a parent document");
          setSaving(false);
          return;
        }
        created = await createDomain(
          {
            documentId: parentDocumentId,
            code,
            name,
            description: description || null,
          },
          token,
        );
      } else if (recordType === "strand") {
        if (!parentDomainId) {
          setError("Please select a parent domain");
          setSaving(false);
          return;
        }
        created = await createStrand(
          {
            domainId: parentDomainId,
            code,
            name,
            description: description || null,
          },
          token,
        );
      } else if (recordType === "sub_strand") {
        if (!parentStrandId) {
          setError("Please select a parent strand");
          setSaving(false);
          return;
        }
        created = await createSubStrand(
          {
            strandId: parentStrandId,
            code,
            name,
            description: description || null,
          },
          token,
        );
      } else {
        // indicator
        if (!resolvedDomainId) {
          setError("Please select a parent");
          setSaving(false);
          return;
        }
        created = await createIndicator(
          {
            domainId: resolvedDomainId,
            strandId:
              indicatorParentLevel === "strand"
                ? parentStrandId
                : indicatorParentLevel === "sub_strand"
                  ? (allSubStrands.find((s) => s.id === parentSubStrandId)
                      ?.strandId ?? null)
                  : null,
            subStrandId:
              indicatorParentLevel === "sub_strand" ? parentSubStrandId : null,
            code,
            title: title || null,
            description,
            ageBand: ageBand || null,
            sourcePage: sourcePage ? Number(sourcePage) : null,
            sourceText: sourceText || null,
          },
          token,
        );
      }

      onCreated(created, recordType);
      handleOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create record");
    } finally {
      setSaving(false);
    }
  }, [
    token,
    recordType,
    code,
    name,
    title,
    description,
    ageBand,
    sourcePage,
    sourceText,
    parentDocumentId,
    parentDomainId,
    parentStrandId,
    parentSubStrandId,
    indicatorParentLevel,
    resolvedDomainId,
    allSubStrands,
    onCreated,
    handleOpenChange,
  ]);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add Standard</DialogTitle>
          <DialogDescription>
            Create a new item in the standards hierarchy.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Record type selector */}
          <div className="grid gap-2">
            <Label htmlFor="add-record-type">Type</Label>
            <Select
              value={recordType}
              onValueChange={(v) => handleRecordTypeChange(v as RecordType)}
            >
              <SelectTrigger id="add-record-type">
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                {(
                  Object.entries(RECORD_TYPE_LABELS) as [RecordType, string][]
                ).map(([key, label]) => (
                  <SelectItem key={key} value={key}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Parent selector — domain → document */}
          {recordType === "domain" && documents && documents.length > 0 && (
            <div className="grid gap-2">
              <Label htmlFor="add-parent-document">Parent Document</Label>
              <Select
                value={parentDocumentId != null ? String(parentDocumentId) : ""}
                onValueChange={(v) => setParentDocumentId(Number(v))}
              >
                <SelectTrigger id="add-parent-document">
                  <SelectValue placeholder="Select document" />
                </SelectTrigger>
                <SelectContent>
                  {documents.map((doc) => (
                    <SelectItem key={doc.id} value={String(doc.id)}>
                      {doc.title} ({doc.country}/{doc.state})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Parent selector — strand → domain */}
          {recordType === "strand" && allDomains.length > 0 && (
            <div className="grid gap-2">
              <Label htmlFor="add-parent-domain">Parent Domain</Label>
              <Select
                value={parentDomainId != null ? String(parentDomainId) : ""}
                onValueChange={(v) => setParentDomainId(Number(v))}
              >
                <SelectTrigger id="add-parent-domain">
                  <SelectValue placeholder="Select domain" />
                </SelectTrigger>
                <SelectContent>
                  {allDomains.map((d) => (
                    <SelectItem key={d.id} value={String(d.id)}>
                      {d.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Parent selector — sub_strand → strand */}
          {recordType === "sub_strand" && allStrands.length > 0 && (
            <div className="grid gap-2">
              <Label htmlFor="add-parent-strand">Parent Strand</Label>
              <Select
                value={parentStrandId != null ? String(parentStrandId) : ""}
                onValueChange={(v) => setParentStrandId(Number(v))}
              >
                <SelectTrigger id="add-parent-strand">
                  <SelectValue placeholder="Select strand" />
                </SelectTrigger>
                <SelectContent>
                  {allStrands.map((s) => (
                    <SelectItem key={s.id} value={String(s.id)}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Indicator parent level selector */}
          {recordType === "indicator" && (
            <>
              <div className="grid gap-2">
                <Label htmlFor="add-indicator-parent-level">Parent Level</Label>
                <Select
                  value={indicatorParentLevel}
                  onValueChange={(v) => {
                    setIndicatorParentLevel(
                      v as "sub_strand" | "strand" | "domain",
                    );
                    setParentDomainId(null);
                    setParentStrandId(null);
                    setParentSubStrandId(null);
                  }}
                >
                  <SelectTrigger id="add-indicator-parent-level">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sub_strand">Sub-Strand</SelectItem>
                    <SelectItem value="strand">Strand</SelectItem>
                    <SelectItem value="domain">Domain</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {indicatorParentLevel === "domain" && allDomains.length > 0 && (
                <div className="grid gap-2">
                  <Label htmlFor="add-ind-parent-domain">Parent Domain</Label>
                  <Select
                    value={parentDomainId != null ? String(parentDomainId) : ""}
                    onValueChange={(v) => setParentDomainId(Number(v))}
                  >
                    <SelectTrigger id="add-ind-parent-domain">
                      <SelectValue placeholder="Select domain" />
                    </SelectTrigger>
                    <SelectContent>
                      {allDomains.map((d) => (
                        <SelectItem key={d.id} value={String(d.id)}>
                          {d.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {indicatorParentLevel === "strand" && allStrands.length > 0 && (
                <div className="grid gap-2">
                  <Label htmlFor="add-ind-parent-strand">Parent Strand</Label>
                  <Select
                    value={parentStrandId != null ? String(parentStrandId) : ""}
                    onValueChange={(v) => setParentStrandId(Number(v))}
                  >
                    <SelectTrigger id="add-ind-parent-strand">
                      <SelectValue placeholder="Select strand" />
                    </SelectTrigger>
                    <SelectContent>
                      {allStrands.map((s) => (
                        <SelectItem key={s.id} value={String(s.id)}>
                          {s.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {indicatorParentLevel === "sub_strand" &&
                allSubStrands.length > 0 && (
                  <div className="grid gap-2">
                    <Label htmlFor="add-ind-parent-substrand">
                      Parent Sub-Strand
                    </Label>
                    <Select
                      value={
                        parentSubStrandId != null
                          ? String(parentSubStrandId)
                          : ""
                      }
                      onValueChange={(v) => setParentSubStrandId(Number(v))}
                    >
                      <SelectTrigger id="add-ind-parent-substrand">
                        <SelectValue placeholder="Select sub-strand" />
                      </SelectTrigger>
                      <SelectContent>
                        {allSubStrands.map((ss) => (
                          <SelectItem key={ss.id} value={String(ss.id)}>
                            {ss.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
            </>
          )}

          {/* Code field — all record types */}
          <div className="grid gap-2">
            <Label htmlFor="add-code">Code</Label>
            <Input
              id="add-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder={`e.g. ${recordType === "indicator" ? "IND-001" : "D1"}`}
            />
          </div>

          {/* Name field — domain, strand, sub_strand */}
          {recordType !== "indicator" && (
            <div className="grid gap-2">
              <Label htmlFor="add-name">Name</Label>
              <Input
                id="add-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
          )}

          {/* Title field — indicator only */}
          {recordType === "indicator" && (
            <div className="grid gap-2">
              <Label htmlFor="add-title">Title</Label>
              <Input
                id="add-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
          )}

          {/* Description field — all record types */}
          <div className="grid gap-2">
            <Label htmlFor="add-description">Description</Label>
            <Textarea
              id="add-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          {/* Indicator-specific fields */}
          {recordType === "indicator" && (
            <>
              <div className="grid gap-2">
                <Label htmlFor="add-age-band">Age Band</Label>
                <Input
                  id="add-age-band"
                  value={ageBand}
                  onChange={(e) => setAgeBand(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="add-source-page">Source Page</Label>
                <Input
                  id="add-source-page"
                  type="number"
                  value={sourcePage}
                  onChange={(e) => setSourcePage(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="add-source-text">Source Text</Label>
                <Textarea
                  id="add-source-text"
                  value={sourceText}
                  onChange={(e) => setSourceText(e.target.value)}
                  rows={3}
                />
              </div>
            </>
          )}

          {/* Error message */}
          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || !code}>
            {saving ? "Creating…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
