export default function Footer() {
  return (
    <footer className="border-t border-border py-8">
      <div className="container flex flex-col items-center gap-3 text-center">
        <div className="flex gap-4">
          <a
            href="#privacy"
            className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Privacy Policy
          </a>
          <span className="text-muted-foreground" aria-hidden="true">
            ·
          </span>
          <a
            href="#terms"
            className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Terms of Service
          </a>
          <span className="text-muted-foreground" aria-hidden="true">
            ·
          </span>
          <a
            href="#contact"
            className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Contact Us
          </a>
        </div>
        <p className="text-sm text-muted-foreground">
          &copy; {new Date().getFullYear()} EdTech Co. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
