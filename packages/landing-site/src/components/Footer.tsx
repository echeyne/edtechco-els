import { Link } from "../router";

const columns = [
  {
    heading: "Who it's for",
    links: [
      { label: "State agencies", href: "/for-states" },
      { label: "Policy researchers", href: "/for-researchers" },
      { label: "Curriculum and edtech", href: "/for-curriculum" },
    ],
  },
  {
    heading: "Learn more",
    links: [
      { label: "Research", href: "/research" },
      { label: "The data", href: "/data" },
      { label: "One-page brief", href: "/brief" },
      { label: "About", href: "/about" },
    ],
  },
  {
    heading: "Site",
    links: [
      { label: "Contact Us", href: "/contact" },
      { label: "Privacy Policy", href: "/privacy" },
      { label: "Terms of Service", href: "/terms" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="border-t border-border py-10">
      <div className="container">
        <div className="grid grid-cols-1 gap-8 text-center sm:grid-cols-3 sm:text-left">
          {columns.map((col) => (
            <div key={col.heading}>
              <p className="mb-3 text-sm font-semibold text-foreground">
                {col.heading}
              </p>
              <ul className="space-y-2">
                {col.links.map((l) => (
                  <li key={l.href}>
                    <Link
                      href={l.href}
                      className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-8 text-center text-sm text-muted-foreground">
          &copy; {new Date().getFullYear()} EdTech Co. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
