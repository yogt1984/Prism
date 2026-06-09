import Link from "next/link";
import Button from "@/components/ui/Button";

const FEATURES = [
  {
    title: "Multi-perspective summaries",
    description:
      "Every story presented through multiple source framings, so you see the full picture.",
  },
  {
    title: "Transparent bias labels",
    description:
      "Each source tagged with a bias label and trust score. No hidden agendas.",
  },
  {
    title: "Personalized briefings",
    description:
      "A daily digest built around your interests, delivered how you want it.",
  },
  {
    title: "Media resonance",
    description:
      "See which stories are gaining traction across the media landscape.",
  },
  {
    title: "Perception pressure",
    description:
      "Track how public sentiment shifts on the topics you care about.",
  },
  {
    title: "No ads, ever",
    description:
      "Subscription-funded. Aligned with readers, not advertisers.",
  },
] as const;

const STEPS = [
  {
    number: "01",
    title: "Sign up and pick your interests",
    description:
      "Choose from 8 categories. Finance, politics, technology, and more.",
  },
  {
    number: "02",
    title: "We curate from hundreds of sources",
    description:
      "AI reads the news, identifies stories, and surfaces multiple perspectives.",
  },
  {
    number: "03",
    title: "Read your briefing, see the bias",
    description:
      "Every source is labeled. Every framing is visible. You decide what to trust.",
  },
] as const;

export default function Home() {
  return (
    <main data-testid="landing-page">
      {/* Hero */}
      <section
        className="min-h-[70vh] flex flex-col items-center justify-center px-4 text-center"
        data-testid="hero-section"
      >
        <h1 className="text-5xl sm:text-6xl font-bold tracking-tight text-gray-900">
          Prism
        </h1>
        <p className="mt-4 max-w-lg text-lg text-gray-500">
          Humans cannot be objective&nbsp;&mdash; neither can AI. We make the
          bias transparent.
        </p>
        <div className="mt-8 flex flex-col sm:flex-row items-center gap-3">
          <Link href="/signup" data-testid="hero-signup-link">
            <Button className="px-6 py-2.5 text-base">Get started</Button>
          </Link>
          <Link href="/pricing" data-testid="hero-pricing-link">
            <Button variant="secondary" className="px-6 py-2.5 text-base">
              See pricing
            </Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section
        className="max-w-4xl mx-auto px-4 py-16 sm:py-24"
        data-testid="features-section"
      >
        <h2 className="text-2xl font-semibold text-gray-900 text-center mb-12">
          What Prism does differently
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
          {FEATURES.map((f) => (
            <div key={f.title}>
              <h3 className="font-semibold text-gray-900">{f.title}</h3>
              <p className="mt-1 text-sm text-gray-500">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section
        className="bg-gray-50 px-4 py-16 sm:py-24"
        data-testid="how-it-works-section"
      >
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-semibold text-gray-900 text-center mb-12">
            How it works
          </h2>
          <ol className="space-y-8">
            {STEPS.map((s) => (
              <li key={s.number}>
                <span className="font-mono text-sm text-violet-600">
                  {s.number}
                </span>
                <h3 className="mt-1 font-semibold text-gray-900">{s.title}</h3>
                <p className="mt-1 text-sm text-gray-500">{s.description}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Philosophy */}
      <section
        className="max-w-2xl mx-auto px-4 py-16 sm:py-24 text-center"
        data-testid="philosophy-section"
      >
        <blockquote className="text-xl sm:text-2xl font-medium text-gray-900 leading-relaxed">
          Most news platforms optimize for engagement. Prism optimizes for
          understanding.
        </blockquote>
      </section>

      {/* Bottom CTA */}
      <section
        className="px-4 py-16 sm:py-24 text-center"
        data-testid="bottom-cta-section"
      >
        <div className="max-w-md mx-auto space-y-4">
          <h2 className="text-2xl font-semibold text-gray-900">
            Start reading with clarity
          </h2>
          <p className="text-sm text-gray-500">
            Free plan available. No credit card required.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Link href="/signup" data-testid="bottom-signup-link">
              <Button className="px-6 py-2.5 text-base">
                Create your account
              </Button>
            </Link>
            <Link href="/pricing" data-testid="bottom-pricing-link">
              <Button variant="secondary" className="px-6 py-2.5 text-base">
                Compare plans
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer
        className="pb-8 text-center text-xs text-gray-400"
        data-testid="landing-footer"
      >
        Prism
      </footer>
    </main>
  );
}

export { FEATURES, STEPS };
