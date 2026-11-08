import { ButtonLink, PageHeader } from "../components/ui";

export default function NotFoundPage() {
  return (
    <PageHeader
      title="Page not found"
      lede="That page doesn't exist. It may have moved when the site was reorganized."
    >
      <ButtonLink href="/">Go to the home page</ButtonLink>
    </PageHeader>
  );
}
