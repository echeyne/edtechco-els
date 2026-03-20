import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import type { Domain, Strand, SubStrand, Indicator } from "@els/shared";
import {
  getDomain,
  getStrand,
  getSubStrand,
  getIndicatorDetail,
  updateDomain,
  updateStrand,
  updateSubStrand,
  updateIndicator,
  verifyDomain,
  verifyStrand,
  verifySubStrand,
  verifyIndicator,
  type DomainDetail,
  type StrandDetail,
  type SubStrandDetail,
  type IndicatorDetail,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, ShieldCheck, Edit, Save, X } from "lucide-react";

type RecordType = "domain" | "strand" | "sub_strand" | "indicator";

// ---------------------------------------------------------------------------
// VerifiedBadge (read-only display)
// ---------------------------------------------------------------------------

function VerifiedBadge({ verified }: { verified: boolean }) {
  return verified ? (
    <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100 shadow-none">
      <ShieldCheck className="mr-1 h-3 w-3" />
      Verified
    </Badge>
  ) : (
    <Badge variant="secondary" className="text-muted-foreground shadow-none">
      Unverified
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// InfoSection — shows a parent entity's info as a read-only card
// ---------------------------------------------------------------------------

function ParentCard({
  type,
  code,
  name,
  description,
  humanVerified,
  linkTo,
}: {
  type: string;
  code: string;
  name: string;
  description?: string | null;
  humanVerified: boolean;
  linkTo: string;
}) {
  return (
    <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {type}
        </span>
        <VerifiedBadge verified={humanVerified} />
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
          {code}
        </span>
        <Link
          to={linkTo}
          className="font-medium hover:text-primary transition-colors"
        >
          {name}
        </Link>
      </div>
      {description && (
        <p className="text-sm text-muted-foreground">{description}</p>
      )}
    </div>
  );
}
// ---------------------------------------------------------------------------
// Main DetailPage
// ---------------------------------------------------------------------------

export default function DetailPage({ recordType }: { recordType: RecordType }) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasEditPermission, token } = useAuth();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Data
  const [data, setData] = useState<
    DomainDetail | StrandDetail | SubStrandDetail | IndicatorDetail | null
  >(null);

  // Edit form state
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [ageBand, setAgeBand] = useState("");
  const [sourcePage, setSourcePage] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [humanVerified, setHumanVerified] = useState(false);

  const populateForm = useCallback(
    (
      record: DomainDetail | StrandDetail | SubStrandDetail | IndicatorDetail,
    ) => {
      setCode(record.code ?? "");
      setHumanVerified(record.humanVerified ?? false);
      if (recordType === "indicator") {
        const ind = record as IndicatorDetail;
        setTitle(ind.title ?? "");
        setDescription(ind.description ?? "");
        setAgeBand(ind.ageBand ?? "");
        setSourcePage(ind.sourcePage != null ? String(ind.sourcePage) : "");
        setSourceText(ind.sourceText ?? "");
      } else {
        const r = record as DomainDetail | StrandDetail | SubStrandDetail;
        setName((r as Domain).name ?? "");
        setDescription((r as Domain).description ?? "");
      }
    },
    [recordType],
  );

  const fetchData = useCallback(async () => {
    const numId = Number(id);
    if (Number.isNaN(numId)) {
      setError("Invalid ID");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      let result:
        | DomainDetail
        | StrandDetail
        | SubStrandDetail
        | IndicatorDetail;
      if (recordType === "domain") result = await getDomain(numId);
      else if (recordType === "strand") result = await getStrand(numId);
      else if (recordType === "sub_strand") result = await getSubStrand(numId);
      else result = await getIndicatorDetail(numId);
      setData(result);
      populateForm(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [id, recordType, populateForm]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleStartEdit = () => {
    if (data) populateForm(data);
    setSaveError(null);
    setEditing(true);
  };

  const handleCancelEdit = () => {
    if (data) populateForm(data);
    setEditing(false);
    setSaveError(null);
  };

  const handleSave = async () => {
    if (!token || !data) return;
    setSaving(true);
    setSaveError(null);
    try {
      let updated: Domain | Strand | SubStrand | Indicator;
      if (recordType === "domain") {
        updated = await updateDomain(
          data.id,
          { code, name, description: description || null },
          token,
        );
      } else if (recordType === "strand") {
        updated = await updateStrand(
          data.id,
          { code, name, description: description || null },
          token,
        );
      } else if (recordType === "sub_strand") {
        updated = await updateSubStrand(
          data.id,
          { code, name, description: description || null },
          token,
        );
      } else {
        updated = await updateIndicator(
          data.id,
          {
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

      // Handle verification change
      if (humanVerified !== (data.humanVerified ?? false)) {
        const verifyFn = {
          domain: verifyDomain,
          strand: verifyStrand,
          sub_strand: verifySubStrand,
          indicator: verifyIndicator,
        }[recordType];
        await verifyFn(data.id, { humanVerified }, token);
        updated = { ...updated, humanVerified };
      }

      setEditing(false);
      // Re-fetch to get full detail with parents
      await fetchData();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const typeLabel = {
    domain: "Domain",
    strand: "Strand",
    sub_strand: "Sub-Strand",
    indicator: "Indicator",
  }[recordType];

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span className="text-sm">
            Loading {typeLabel.toLowerCase()} details…
          </span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <p className="text-destructive">{error ?? "Not found"}</p>
        <Button variant="outline" onClick={() => navigate(-1)}>
          Go Back
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate(-1)}
            aria-label="Go back"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {typeLabel}
            </span>
            <h2 className="text-xl font-semibold text-foreground">
              {recordType === "indicator"
                ? ((data as IndicatorDetail).title ??
                  (data as IndicatorDetail).description)
                : (data as Domain).name}
            </h2>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!editing && <VerifiedBadge verified={data.humanVerified} />}
          {hasEditPermission && !editing && (
            <Button variant="outline" size="sm" onClick={handleStartEdit}>
              <Edit className="mr-2 h-4 w-4" /> Edit
            </Button>
          )}
        </div>
      </div>

      {/* Parent cards */}
      {recordType !== "domain" && (
        <div className="space-y-3">
          {(data as StrandDetail | SubStrandDetail | IndicatorDetail)
            .domain && (
            <ParentCard
              type="Domain"
              code={
                (data as StrandDetail | SubStrandDetail | IndicatorDetail)
                  .domain!.code
              }
              name={
                (data as StrandDetail | SubStrandDetail | IndicatorDetail)
                  .domain!.name
              }
              description={
                (data as StrandDetail | SubStrandDetail | IndicatorDetail)
                  .domain!.description
              }
              humanVerified={
                (data as StrandDetail | SubStrandDetail | IndicatorDetail)
                  .domain!.humanVerified
              }
              linkTo={`/domains/${(data as StrandDetail | SubStrandDetail | IndicatorDetail).domain!.id}`}
            />
          )}
          {(recordType === "sub_strand" || recordType === "indicator") &&
            (data as SubStrandDetail | IndicatorDetail).strand && (
              <ParentCard
                type="Strand"
                code={(data as SubStrandDetail | IndicatorDetail).strand!.code}
                name={(data as SubStrandDetail | IndicatorDetail).strand!.name}
                description={
                  (data as SubStrandDetail | IndicatorDetail).strand!
                    .description
                }
                humanVerified={
                  (data as SubStrandDetail | IndicatorDetail).strand!
                    .humanVerified
                }
                linkTo={`/strands/${(data as SubStrandDetail | IndicatorDetail).strand!.id}`}
              />
            )}
          {recordType === "indicator" &&
            (data as IndicatorDetail).subStrand && (
              <ParentCard
                type="Sub-Strand"
                code={(data as IndicatorDetail).subStrand!.code}
                name={(data as IndicatorDetail).subStrand!.name}
                description={(data as IndicatorDetail).subStrand!.description}
                humanVerified={
                  (data as IndicatorDetail).subStrand!.humanVerified
                }
                linkTo={`/sub-strands/${(data as IndicatorDetail).subStrand!.id}`}
              />
            )}
        </div>
      )}

      {/* Detail card */}
      <div className="rounded-lg border bg-card p-6 shadow-sm space-y-4">
        {editing ? (
          <>
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="detail-code">Code</Label>
                <Input
                  id="detail-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </div>

              {recordType !== "indicator" ? (
                <>
                  <div className="grid gap-2">
                    <Label htmlFor="detail-name">Name</Label>
                    <Input
                      id="detail-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="detail-description">Description</Label>
                    <Textarea
                      id="detail-description"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={3}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div className="grid gap-2">
                    <Label htmlFor="detail-title">Title</Label>
                    <Input
                      id="detail-title"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="detail-description">Description</Label>
                    <Textarea
                      id="detail-description"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={3}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="detail-age-band">Age Band</Label>
                    <Input
                      id="detail-age-band"
                      value={ageBand}
                      onChange={(e) => setAgeBand(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="detail-source-page">Source Page</Label>
                    <Input
                      id="detail-source-page"
                      type="number"
                      value={sourcePage}
                      onChange={(e) => setSourcePage(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="detail-source-text">Source Text</Label>
                    <Textarea
                      id="detail-source-text"
                      value={sourceText}
                      onChange={(e) => setSourceText(e.target.value)}
                      rows={3}
                    />
                  </div>
                </>
              )}

              <div className="flex items-center gap-2">
                <Checkbox
                  id="detail-verified"
                  checked={humanVerified}
                  onCheckedChange={(checked) =>
                    setHumanVerified(checked === true)
                  }
                />
                <Label htmlFor="detail-verified" className="cursor-pointer">
                  Human Verified
                </Label>
              </div>

              {saveError && (
                <p className="text-sm text-destructive" role="alert">
                  {saveError}
                </p>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                onClick={handleCancelEdit}
                disabled={saving}
              >
                <X className="mr-2 h-4 w-4" /> Cancel
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                <Save className="mr-2 h-4 w-4" /> {saving ? "Saving…" : "Save"}
              </Button>
            </div>
          </>
        ) : (
          <div className="space-y-4">
            <DetailRow label="Code" value={data.code} mono />

            {recordType !== "indicator" ? (
              <>
                <DetailRow label="Name" value={(data as Domain).name} />
                <DetailRow
                  label="Description"
                  value={(data as Domain).description}
                />
              </>
            ) : (
              <>
                <DetailRow
                  label="Title"
                  value={(data as IndicatorDetail).title}
                />
                <DetailRow
                  label="Description"
                  value={(data as IndicatorDetail).description}
                />
                <DetailRow
                  label="Age Band"
                  value={(data as IndicatorDetail).ageBand}
                />
                <DetailRow
                  label="Source Page"
                  value={
                    (data as IndicatorDetail).sourcePage != null
                      ? String((data as IndicatorDetail).sourcePage)
                      : null
                  }
                />
                <DetailRow
                  label="Source Text"
                  value={(data as IndicatorDetail).sourceText}
                />
              </>
            )}

            <DetailRow label="Human Verified" value={null}>
              <VerifiedBadge verified={data.humanVerified} />
            </DetailRow>

            {data.verifiedAt && (
              <DetailRow
                label="Verified At"
                value={new Date(
                  data.verifiedAt as unknown as string,
                ).toLocaleString()}
              />
            )}
            {data.verifiedBy && (
              <DetailRow label="Verified By" value={data.verifiedBy} />
            )}
            {data.editedAt && (
              <DetailRow
                label="Last Edited"
                value={new Date(
                  data.editedAt as unknown as string,
                ).toLocaleString()}
              />
            )}
            {data.editedBy && (
              <DetailRow label="Edited By" value={data.editedBy} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DetailRow helper
// ---------------------------------------------------------------------------

function DetailRow({
  label,
  value,
  mono,
  children,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2 items-start">
      <span className="text-sm font-medium text-muted-foreground">{label}</span>
      {children ? (
        <div className="w-fit">{children}</div>
      ) : (
        <span
          className={`text-sm ${mono ? "font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded inline-block w-fit" : "text-foreground"}`}
        >
          {value ?? <span className="text-muted-foreground/50 italic">—</span>}
        </span>
      )}
    </div>
  );
}
