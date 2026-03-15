import { useState, useEffect, useCallback } from "react";
import type {
  Domain,
  Strand,
  SubStrand,
  Indicator,
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

  // UI state
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Populate form when record changes
  useEffect(() => {
    if (!record) return;
    setCode(record.code ?? "");
    setHumanVerified(record.humanVerified ?? false);
    setError(null);

    if (recordType === "indicator") {
      const ind = record as Indicator;
      setTitle(ind.title ?? "");
      setDescription(ind.description ?? "");
      setAgeBand(ind.ageBand ?? "");
      setSourcePage(ind.sourcePage != null ? String(ind.sourcePage) : "");
      setSourceText(ind.sourceText ?? "");
    } else {
      const rec = record as Domain | Strand | SubStrand;
      setName(rec.name ?? "");
      setDescription(rec.description ?? "");
    }
  }, [record, recordType]);

  const handleVerifyChange = useCallback(
    async (checked: boolean) => {
      if (!token) return;
      setVerifying(true);
      setError(null);
      try {
        const verifyFn = {
          domain: verifyDomain,
          strand: verifyStrand,
          sub_strand: verifySubStrand,
          indicator: verifyIndicator,
        }[recordType];
        await verifyFn(record.id, { humanVerified: checked }, token);
        setHumanVerified(checked);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to update verification",
        );
      } finally {
        setVerifying(false);
      }
    },
    [token, record.id, recordType],
  );

  const handleSave = useCallback(async () => {
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      let updated: Domain | Strand | SubStrand | Indicator;

      if (recordType === "indicator") {
        const data: UpdateIndicatorRequest = {
          code,
          title: title || null,
          description,
          ageBand: ageBand || null,
          sourcePage: sourcePage ? Number(sourcePage) : null,
          sourceText: sourceText || null,
        };
        updated = await updateIndicator(record.id, data, token);
      } else {
        const data: UpdateDomainRequest | UpdateStrandRequest | UpdateSubStrandRequest = {
          code,
          name,
          description: description || null,
        };
        const updateFn = {
          domain: updateDomain,
          strand: updateStrand,
          sub_strand: updateSubStrand,
        }[recordType] as (
          id: number,
          data: UpdateDomainRequest,
          token: string,
        ) => Promise<Domain | Strand | SubStrand>;
        updated = await updateFn(record.id, data, token);
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
    recordType,
    code,
    name,
    title,
    description,
    ageBand,
    sourcePage,
    sourceText,
    onSave,
    onOpenChange,
  ]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit {RECORD_TYPE_LABELS[recordType]}</DialogTitle>
          <DialogDescription>
            Update the fields below and click save.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
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
              disabled={verifying}
              onCheckedChange={(checked) =>
                handleVerifyChange(checked === true)
              }
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
          <Button onClick={handleSave} disabled={saving || verifying}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
