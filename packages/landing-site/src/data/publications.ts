import { PAPER, arxivUrl } from "./site";

/**
 * Publications, talks and press for /about. This page doubles as an NIW
 * exhibit, so list only things that exist: a submission goes in once it is
 * submitted, a talk once it is confirmed, press once it is published.
 */

export type PublicationStatus =
  | "preprint"
  | "forthcoming"
  | "submitted"
  | "accepted"
  | "published";

export interface Publication {
  title: string;
  authors: string[];
  venue: string;
  year: number;
  status: PublicationStatus;
  url: string | null;
}

export interface Talk {
  title: string;
  event: string;
  date: string; // ISO yyyy-mm-dd
  url: string | null;
}

export interface PressMention {
  outlet: string;
  title: string;
  date: string; // ISO yyyy-mm-dd
  url: string;
}

export const publications: Publication[] = [
  {
    title: PAPER.title,
    authors: PAPER.authors,
    venue: "arXiv preprint",
    year: PAPER.year,
    status: PAPER.arxivId ? "preprint" : "forthcoming",
    url: arxivUrl(),
  },
];

export const talks: Talk[] = [];

export const press: PressMention[] = [];

export const STATUS_LABEL: Record<PublicationStatus, string> = {
  preprint: "Preprint",
  forthcoming: "Forthcoming",
  submitted: "Under review",
  accepted: "Accepted",
  published: "Published",
};
