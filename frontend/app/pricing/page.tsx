"use client";

import { useSession } from "next-auth/react";
import Link from "next/link";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { useUserProfile, useCheckout } from "@/lib/hooks";

const TIERS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    features: [
      { text: "1 topic category", included: true },
      { text: "Up to 10 stories per briefing", included: true },
      { text: "Email delivery", included: true },
      { text: "3 perception keywords", included: true },
      { text: "Audio briefings", included: false },
      { text: "JSON API access", included: false },
      { text: "All 8 topic categories", included: false },
      { text: "Up to 25 stories per briefing", included: false },
    ],
  },
  {
    name: "Pro",
    price: "$7",
    period: "/month",
    features: [
      { text: "All 8 topic categories", included: true },
      { text: "Up to 25 stories per briefing", included: true },
      { text: "Email, JSON & audio delivery", included: true },
      { text: "Unlimited perception keywords", included: true },
      { text: "Audio briefings", included: true },
      { text: "JSON API access", included: true },
      { text: "Priority support", included: true },
      { text: "No ads, ever", included: true },
    ],
  },
] as const;

export default function PricingPage() {
  const { data: session, status } = useSession();
  const userId = (session?.user as Record<string, unknown> | undefined)
    ?.id as number | undefined;

  const { data: user } = useUserProfile(userId);
  const checkout = useCheckout(userId);

  const isAuthenticated = status === "authenticated";
  const isPro = user?.is_pro ?? false;

  return (
    <main
      className="max-w-4xl mx-auto px-4 py-12 sm:py-16"
      data-testid="pricing-page"
    >
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold text-gray-900 mb-3">
          Simple, transparent pricing
        </h1>
        <p className="text-gray-500 max-w-lg mx-auto">
          No ads. No data selling. Just multi-perspective news briefings that
          make bias visible.
        </p>
      </div>

      <div
        className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12"
        data-testid="tier-grid"
      >
        {TIERS.map((tier) => {
          const isCurrentPlan = isAuthenticated && (
            (tier.name === "Pro" && isPro) ||
            (tier.name === "Free" && !isPro)
          );
          const isProTier = tier.name === "Pro";

          return (
            <Card
              key={tier.name}
              variant={isProTier ? "alert" : "default"}
              className="flex flex-col"
              data-testid={`tier-${tier.name.toLowerCase()}`}
            >
              <div className="flex items-center gap-2 mb-4">
                <h2 className="text-xl font-semibold">{tier.name}</h2>
                {isCurrentPlan && (
                  <Badge
                    color="bg-green-100 text-green-700"
                    data-testid="current-plan-badge"
                  >
                    Current plan
                  </Badge>
                )}
              </div>

              <p className="mb-6">
                <span className="text-3xl font-bold text-gray-900">
                  {tier.price}
                </span>
                <span className="text-sm text-gray-500 ml-1">
                  {tier.period}
                </span>
              </p>

              <ul className="space-y-3 mb-8 flex-1">
                {tier.features.map((f) => (
                  <li
                    key={f.text}
                    className="flex items-start gap-2 text-sm"
                  >
                    {f.included ? (
                      <svg
                        className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    ) : (
                      <svg
                        className="h-4 w-4 text-gray-300 mt-0.5 flex-shrink-0"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    )}
                    <span
                      className={
                        f.included ? "text-gray-700" : "text-gray-400"
                      }
                    >
                      {f.text}
                    </span>
                  </li>
                ))}
              </ul>

              <div className="mt-auto">
                {isProTier ? (
                  isAuthenticated ? (
                    isPro ? (
                      <Link href="/settings" data-testid="manage-link">
                        <Button variant="secondary" fullWidth>
                          Manage Subscription
                        </Button>
                      </Link>
                    ) : (
                      <Button
                        onClick={() => checkout.mutate()}
                        disabled={checkout.isPending}
                        fullWidth
                        data-testid="upgrade-btn"
                      >
                        {checkout.isPending
                          ? "Redirecting..."
                          : "Upgrade to Pro"}
                      </Button>
                    )
                  ) : (
                    <Link href="/signup" data-testid="signup-link">
                      <Button fullWidth>Get Started</Button>
                    </Link>
                  )
                ) : isAuthenticated ? (
                  isPro ? null : (
                    <p
                      className="text-center text-sm text-gray-400"
                      data-testid="free-current"
                    >
                      Your current plan
                    </p>
                  )
                ) : (
                  <Link href="/signup" data-testid="signup-free-link">
                    <Button variant="secondary" fullWidth>
                      Sign Up Free
                    </Button>
                  </Link>
                )}
              </div>

              {checkout.isError && isProTier && (
                <p
                  className="text-sm text-red-600 mt-2 text-center"
                  data-testid="checkout-error"
                >
                  Something went wrong. Please try again.
                </p>
              )}
            </Card>
          );
        })}
      </div>

      <div className="text-center text-sm text-gray-400" data-testid="pricing-footer">
        <p>
          Subscriptions are billed monthly. Cancel anytime from your{" "}
          <Link href="/settings" className="text-violet-600 hover:underline">
            settings
          </Link>
          .
        </p>
      </div>
    </main>
  );
}

export { TIERS };
