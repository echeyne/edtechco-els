import { useEffect } from "react";

interface PrivacyPageProps {
  onBack: () => void;
}

export default function PrivacyPage({ onBack }: PrivacyPageProps) {
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

      <h1 className="text-3xl font-bold text-foreground">Privacy Policy</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Last updated: April 5, 2026
      </p>
      <div className="mt-6 space-y-6 text-muted-foreground leading-relaxed">
        <p>
          EdTech Co. (&quot;we&quot;, &quot;us&quot;, or &quot;our&quot;)
          respects your privacy. This Privacy Policy explains how we collect,
          use, and protect your information when you use our website and
          services.
        </p>
        <h2 className="text-xl font-semibold text-foreground">
          Information We Collect
        </h2>
        <p>
          We may collect information you provide directly, such as your name,
          email address, and any other details you submit through forms on our
          site. We also automatically collect certain technical data, including
          your IP address, browser type, and pages visited, through cookies and
          similar technologies.
        </p>
        <h2 className="text-xl font-semibold text-foreground">
          How We Use Your Information
        </h2>
        <ul className="list-disc space-y-1 pl-6">
          <li>To provide and improve our services</li>
          <li>To communicate with you about updates or inquiries</li>
          <li>To analyze usage trends and enhance user experience</li>
          <li>To comply with legal obligations</li>
        </ul>
        <h2 className="text-xl font-semibold text-foreground">Data Sharing</h2>
        <p>
          We do not sell your personal information. We may share data with
          trusted third-party service providers who assist us in operating our
          website, provided they agree to keep your information confidential.
        </p>
        <h2 className="text-xl font-semibold text-foreground">Data Security</h2>
        <p>
          We implement reasonable security measures to protect your information.
          However, no method of transmission over the internet is completely
          secure, and we cannot guarantee absolute security.
        </p>
        <h2 className="text-xl font-semibold text-foreground">Your Rights</h2>
        <p>
          You may request access to, correction of, or deletion of your personal
          data at any time by contacting us. Where applicable, you may also opt
          out of marketing communications.
        </p>
        <h2 className="text-xl font-semibold text-foreground">
          Changes to This Policy
        </h2>
        <p>
          We may update this Privacy Policy from time to time. We will notify
          you of any changes by posting the new policy on this page and updating
          the &quot;Last updated&quot; date.
        </p>
      </div>
    </div>
  );
}
