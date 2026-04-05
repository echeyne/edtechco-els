import { useEffect } from "react";

interface TermsPageProps {
  onBack: () => void;
}

export default function TermsPage({ onBack }: TermsPageProps) {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="container mx-auto max-w-3xl px-4 py-16">
      <button
        onClick={onBack}
        className="mb-8 inline-flex items-center text-sm font-medium text-primary hover:underline"
      >
        &larr; Back to Home
      </button>

      <h1 className="text-3xl font-bold text-foreground">Terms of Service</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Last updated: April 5, 2026
      </p>
      <div className="mt-6 space-y-6 text-muted-foreground leading-relaxed">
        <p>
          By accessing or using the EdTech Co. website and services, you agree
          to be bound by these Terms of Service. If you do not agree, please do
          not use our services.
        </p>
        <h2 className="text-xl font-semibold text-foreground">
          Use of Services
        </h2>
        <p>
          You agree to use our services only for lawful purposes and in
          accordance with these Terms. You must not use our services in any way
          that could damage, disable, or impair the site or interfere with any
          other party&apos;s use.
        </p>
        <h2 className="text-xl font-semibold text-foreground">
          Intellectual Property
        </h2>
        <p>
          All content on this site, including text, graphics, logos, and
          software, is the property of EdTech Co. or its licensors and is
          protected by applicable intellectual property laws. You may not
          reproduce, distribute, or create derivative works without our prior
          written consent.
        </p>
        <h2 className="text-xl font-semibold text-foreground">
          Disclaimer of Warranties
        </h2>
        <p>
          Our services are provided &quot;as is&quot; and &quot;as
          available&quot; without warranties of any kind, either express or
          implied. We do not guarantee that our services will be uninterrupted,
          error-free, or secure.
        </p>
        <h2 className="text-xl font-semibold text-foreground">
          Limitation of Liability
        </h2>
        <p>
          To the fullest extent permitted by law, EdTech Co. shall not be liable
          for any indirect, incidental, special, or consequential damages
          arising from your use of our services.
        </p>
        <h2 className="text-xl font-semibold text-foreground">Governing Law</h2>
        <p>
          These Terms shall be governed by and construed in accordance with
          applicable laws, without regard to conflict of law principles.
        </p>
        <h2 className="text-xl font-semibold text-foreground">
          Changes to These Terms
        </h2>
        <p>
          We reserve the right to modify these Terms at any time. Continued use
          of our services after changes constitutes acceptance of the updated
          Terms.
        </p>
        <h2 className="text-xl font-semibold text-foreground">Contact Us</h2>
        <p>
          If you have questions about these Terms or our Privacy Policy, please{" "}
          <a
            href="#contact"
            className="text-foreground underline underline-offset-4 hover:text-primary"
          >
            contact us
          </a>{" "}
          through the information provided on our website.
        </p>
      </div>
    </div>
  );
}
