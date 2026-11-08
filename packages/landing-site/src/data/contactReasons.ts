/**
 * Reasons offered in the contact form's dropdown. Pages link to
 * `/contact?reason=<key>` to preselect one, and the key goes into the email
 * subject so replies can be sorted by audience.
 */
export const CONTACT_REASONS = [
  { key: "general", label: "General question" },
  { key: "validate-state", label: "Validate my state's data" },
  { key: "request-state", label: "Request a state" },
  { key: "research-data", label: "Data access for research" },
  { key: "curriculum-data", label: "Data access for curriculum or edtech" },
  { key: "pilot", label: "Pilot or partnership" },
  { key: "speaking", label: "Speaking, webinar or press" },
] as const;

export type ContactReasonKey = (typeof CONTACT_REASONS)[number]["key"];

export function isContactReason(v: string | null): v is ContactReasonKey {
  return CONTACT_REASONS.some((r) => r.key === v);
}

export function contactReasonLabel(key: ContactReasonKey): string {
  return CONTACT_REASONS.find((r) => r.key === key)!.label;
}
