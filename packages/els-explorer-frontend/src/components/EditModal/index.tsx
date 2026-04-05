import { useState, useEffect, useCallback, useMemo } from "react";
import type {
  Document,
  Domain,
  Strand,
  SubStrand,
  Indicator,
  HierarchyResponse,
  UpdateDomainRequest,
  UpdateStrandRequest,
  UpdateSubStrandRequest,
  UpdateIndicatorRequest,
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
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  updateDomain,
  updateStrand,
  updateSubStrand,
  updateIndicator,
  verifyDomain,
  verifyStrand,
  verifySubStrand,
  verifyIndicator,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

type RecordType = "domain" | "strand" | "sub_strand" | "indicator";

export interface EditModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  record: Domain | Strand | SubStrand | Indicator;
  recordType: RecordType;
  onSave: (updated: Domain | Strand | SubStrand | Indicator) => void;
  /** All loaded documents — needed for parent selectors */
  documents?: Document[];
  /** All loaded hierarchies keyed by document id — needed for parent selectors */
  hierarchies?: Map<number, HierarchyResponse>;
}

const RECORD_TYPE_LABELS: Record<RecordType, string> = {
  domain: "Domain",
  strand: "Strand",
  sub_strand: "Sub-Strand",
  indicator: "Indicator",
};

export function EditModal({
  open,
  onOpenChange,
  record,
  recordType,
  onSave,
  documents,
  hierarchies,
}: EditModalProps) {
  const { token } = useAuth();

  // Form state
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [ageBand, setAgeBand] = useState("");
  const [sourcePage, setSourcePage] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [humanVerified, setHumanVerified] = useState(false);

  // Parent ID state for re-parenting
  const [parentDocumentId, setParentDocumentId] = useState<number | null>(null);
  const [parentDomainId, setParentDomainId] = useState<number | null>(null);
  const [parentStrandId, setParentStrandId] = useState<number | null>(null);
  const [parentSubStrandId, setParentSubStrandId] = useState<number | null>(
    null,
  );

  // UI state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Populate form when record changes
  useEffect(() => {
    if (!record) return;
    setCode(record.code ?? "");
    setHumanVerified(true);
    setError(null);

    if (recordType === "domain") {
      const dom = record as Domain;
      setName(dom.name ?? "");
      setDescription(dom.description ?? "");
      setParentDocumentId(dom.documentId);
    } else if (recordType === "strand") {
      const s = record as Strand;
      setName(s.name ?? "");
      setDescription(s.description ?? "");
      setParentDomainId(s.domainId);
    } else if (recordType === "sub_strand") {
      const ss = record as SubStrand;
      setName(ss.name ?? "");
      setDescription(ss.description ?? "");
      setParentStrandId(ss.strandId);
    } else if (recordType === "indicator") {
      const ind = record as Indicator;
      setTitle(ind.title ?? "");
      setDescription(ind.description ?? "");
      setAgeBand(ind.ageBand ?? "");
      setSourcePage(ind.sourcePage != null ? String(ind.sourcePage) : "");
      setSourceText(ind.sourceText ?? "");
      setParentSubStrandId(ind.subStrandId ?? null);
      setParentStrandId(ind.strandId ?? null);
    }
  }, [record, recordType]);

  // Build parent option lists from hierarchies
  const allDomains = useMemo(() => {
    if (!hierarchies) return [];
    const result: { id: number; label: string }[] = [];
    for (const [, h] of hierarchies) {
      for (const d of h.domains) {
        result.push({ id: d.id, label: `${d.code} — ${d.name}` });
      }
    }
    return result;
  }, [hierarchies]);

  const allStrands = useMemo(() => {
    if (!hierarchies) return [];
    const result: { id: number; label: string }[] = [];
    for (const [, h] of hierarchies) {
      for (const d of h.domains) {
        for (const s of d.strands) {
          result.push({ id: s.id, label: `${s.code} — ${s.name}` });
        }
      }
    }
    return result;
  }, [hierarchies]);

  const allSubStrands = useMemo(() => {
    if (!hierarchies) return [];
    const result: { id: number; label: string }[] = [];
    for (const [, h] of hierarchies) {
      for (const d of h.domains) {
        for (const s of d.strands) {
          for (const ss of s.subStrands) {
            result.push({ id: ss.id, label: `${ss.code} — ${ss.name}` });
          }
        }
      }
    }
    return result;
  }, [hierarchies]);

  const handleSave = useCallback(async () => {
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      let updated: Domain | Strand | SubStrand | Indicator;

      if (recordType === "indicator") {
        const ind = record as Indicator;
        const isDirectStrandChild = ind.subStrandId == null;
        const data: UpdateIndicatorRequest = {
          code,
          title: title || null,
          description,
          ageBand: ageBand || null,
          sourcePage: sourcePage ? Number(sourcePage) : null,
          sourceText: sourceText || null,
          subStrandId: isDirectStrandChild ? null : parentSubStrandId,
          strandId: isDirectStrandChild ? parentStrandId : undefined,
        };
        updated = await updateIndicator(record.id, data, token);
      } else if (recordType === "domain") {
        const data: UpdateDomainRequest = {
          code,
          name,
          description: description || null,
          documentId: parentDocumentId ?? undefined,
        };
        updated = await updateDomain(record.id, data, token);
      } else if (recordType === "strand") {
        const data: UpdateStrandRequest = {
          code,
          name,
          description: description || null,
          domainId: parentDomainId ?? undefined,
        };
        updated = await updateStrand(record.id, data, token);
      } else {
        // sub_strand
        const data: UpdateSubStrandRequest = {
          code,
          name,
          description: description || null,
          strandId: parentStrandId ?? undefined,
        };
        updated = await updateSubStrand(record.id, data, token);
      }

      // Persist verification status if it changed from the record's original value
      if (humanVerified !== (record.humanVerified ?? false)) {
        const verifyFn = {
          domain: verifyDomain,
          strand: verifyStrand,
          sub_strand: verifySubStrand,
          indicator: verifyIndicator,
        }[recordType];
        await verifyFn(record.id, { humanVerified }, token);
        updated = { ...updated, humanVerified };
      }

      onSave(updated);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save changes");
    } finally {
      setSaving(false);
    }
  }, [
    token,
    record.id,
    record.humanVerified,
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
    humanVerified,
    onSave,
    onOpenChange,
  ]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit {RECORD_TYPE_LABELS[recordType]}</DialogTitle>
          <DialogDescription>
            Update the fields below and click save.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Parent selector — domain → document */}
          {recordType === "domain" && documents && documents.length > 0 && (
            <div className="grid gap-2">
              <Label htmlFor="edit-parent-document">Parent Document</Label>
              <Select
                value={parentDocumentId != null ? String(parentDocumentId) : ""}
                onValueChange={(v) => setParentDocumentId(Number(v))}
              >
                <SelectTrigger id="edit-parent-document">
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
              <Label htmlFor="edit-parent-domain">Parent Domain</Label>
              <Select
                value={parentDomainId != null ? String(parentDomainId) : ""}
                onValueChange={(v) => setParentDomainId(Number(v))}
              >
                <SelectTrigger id="edit-parent-domain">
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
              <Label htmlFor="edit-parent-strand">Parent Strand</Label>
              <Select
                value={parentStrandId != null ? String(parentStrandId) : ""}
                onValueChange={(v) => setParentStrandId(Number(v))}
              >
                <SelectTrigger id="edit-parent-strand">
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

          {/* Parent selector — indicator → sub_strand */}
          {recordType === "indicator" &&
            (record as Indicator).subStrandId != null &&
            allSubStrands.length > 0 && (
              <div className="grid gap-2">
                <Label htmlFor="edit-parent-substrand">Parent Sub-Strand</Label>
                <Select
                  value={
                    parentSubStrandId != null ? String(parentSubStrandId) : ""
                  }
                  onValueChange={(v) => setParentSubStrandId(Number(v))}
                >
                  <SelectTrigger id="edit-parent-substrand">
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

          {/* Parent selector — indicator → strand (direct child, no sub-strand) */}
          {recordType === "indicator" &&
            (record as Indicator).subStrandId == null &&
            allStrands.length > 0 && (
              <div className="grid gap-2">
                <Label htmlFor="edit-parent-strand-indicator">
                  Parent Strand
                </Label>
                <Select
                  value={parentStrandId != null ? String(parentStrandId) : ""}
                  onValueChange={(v) => setParentStrandId(Number(v))}
                >
                  <SelectTrigger id="edit-parent-strand-indicator">
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

          {/* Code field — all record types */}
          <div className="grid gap-2">
            <Label htmlFor="edit-code">Code</Label>
            <Input
              id="edit-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </div>

          {/* Name field — domain, strand, sub_strand */}
          {recordType !== "indicator" && (
            <div className="grid gap-2">
              <Label htmlFor="edit-name">Name</Label>
              <Input
                id="edit-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
          )}

          {/* Title field — indicator only */}
          {recordType === "indicator" && (
            <div className="grid gap-2">
              <Label htmlFor="edit-title">Title</Label>
              <Input
                id="edit-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
          )}

          {/* Description field — all record types */}
          <div className="grid gap-2">
            <Label htmlFor="edit-description">Description</Label>
            <Textarea
              id="edit-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          {/* Indicator-specific fields */}
          {recordType === "indicator" && (
            <>
              <div className="grid gap-2">
                <Label htmlFor="edit-age-band">Age Band</Label>
                <Input
                  id="edit-age-band"
                  value={ageBand}
                  onChange={(e) => setAgeBand(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-source-page">Source Page</Label>
                <Input
                  id="edit-source-page"
                  type="number"
                  value={sourcePage}
                  onChange={(e) => setSourcePage(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-source-text">Source Text</Label>
                <Textarea
                  id="edit-source-text"
                  value={sourceText}
                  onChange={(e) => setSourceText(e.target.value)}
                  rows={3}
                />
              </div>
            </>
          )}

          {/* Human verified checkbox */}
          <div className="flex items-center gap-2">
            <Checkbox
              id="edit-human-verified"
              checked={humanVerified}
              onCheckedChange={(checked) => setHumanVerified(checked === true)}
            />
            <Label htmlFor="edit-human-verified" className="cursor-pointer">
              Human Verified
            </Label>
          </div>

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
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
