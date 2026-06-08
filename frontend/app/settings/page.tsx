"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import InterestToggle from "@/components/settings/InterestToggle";
import DepthSlider from "@/components/settings/DepthSlider";
import FormatSelector from "@/components/settings/FormatSelector";
import FeatureComparison from "@/components/settings/FeatureComparison";
import PlanBadge from "@/components/settings/PlanBadge";
import SaveButton from "@/components/settings/SaveButton";
import UpgradeCard from "@/components/subscription/UpgradeCard";
import GracePeriodWarning from "@/components/subscription/GracePeriodWarning";
import SuccessBanner from "@/components/subscription/SuccessBanner";
import { useUserProfile, useUpdateUser, useCheckout, usePortal } from "@/lib/hooks";
import { CATEGORIES, type BriefingFormat } from "@/lib/types";

function setsEqual(a: Set<string>, b: Set<string>) {
  if (a.size !== b.size) return false;
  for (const v of a) if (!b.has(v)) return false;
  return true;
}

export default function SettingsPage() {
  const { data: session } = useSession();
  const userId = (session?.user as Record<string, unknown> | undefined)
    ?.id as number | undefined;

  const searchParams = useSearchParams();
  const { data: user, isLoading, error } = useUserProfile(userId);
  const updateUser = useUpdateUser(userId);
  const checkout = useCheckout(userId);
  const portal = usePortal(userId);

  // Post-checkout state
  const [showSuccess, setShowSuccess] = useState(false);
  const [showCancelled, setShowCancelled] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  // Detect return from Stripe
  useEffect(() => {
    if (searchParams?.get("upgraded") === "true") {
      setShowSuccess(true);
    }
    if (searchParams?.get("upgrade_cancelled") === "true") {
      setShowCancelled(true);
      const timer = setTimeout(() => setShowCancelled(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [searchParams]);

  // Profile form state
  const [name, setName] = useState("");
  // Interest form state
  const [interests, setInterests] = useState<Set<string>>(new Set());
  // Preferences form state
  const [format, setFormat] = useState<BriefingFormat>("email");
  const [depth, setDepth] = useState(10);

  // Error state
  const [saveError, setSaveError] = useState<string | null>(null);

  // Sync form state when user data loads
  useEffect(() => {
    if (user) {
      setName(user.name);
      setInterests(new Set(user.interests.split(",").filter(Boolean)));
      setFormat(user.preferred_format);
      setDepth(user.briefing_depth);
    }
  }, [user]);

  const saveProfile = useCallback(() => {
    setSaveError(null);
    updateUser.mutate(
      { name },
      { onError: (err) => setSaveError(err.message) },
    );
  }, [name, updateUser]);

  const saveInterests = useCallback(() => {
    setSaveError(null);
    updateUser.mutate(
      { interests: [...interests].join(",") },
      { onError: (err) => setSaveError(err.message) },
    );
  }, [interests, updateUser]);

  const savePreferences = useCallback(() => {
    setSaveError(null);
    updateUser.mutate(
      { preferred_format: format, briefing_depth: depth },
      { onError: (err) => setSaveError(err.message) },
    );
  }, [format, depth, updateUser]);

  const handleUpgrade = useCallback(() => {
    setCheckoutError(null);
    checkout.mutate(undefined, {
      onError: (err) => setCheckoutError(err.message),
    });
  }, [checkout]);

  const handleManage = useCallback(() => {
    setCheckoutError(null);
    portal.mutate(undefined, {
      onError: (err) => setCheckoutError(err.message),
    });
  }, [portal]);

  const toggleInterest = (cat: string) => {
    setInterests((prev) => {
      const next = new Set(prev);
      next.has(cat) ? next.delete(cat) : next.add(cat);
      return next;
    });
  };

  if (isLoading) {
    return (
      <main className="max-w-2xl mx-auto px-4 py-8" data-testid="settings-loading">
        <h1 className="text-2xl font-bold mb-6">Settings</h1>
        <div className="space-y-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 bg-gray-100 animate-pulse rounded-lg" />
          ))}
        </div>
      </main>
    );
  }

  if (error || !user) {
    return (
      <main className="max-w-2xl mx-auto px-4 py-8" data-testid="settings-error">
        <h1 className="text-2xl font-bold mb-4">Settings</h1>
        <p className="text-gray-500 mb-4">Could not load settings</p>
        <button
          onClick={() => window.location.reload()}
          className="text-sm text-violet-600 hover:underline"
          data-testid="retry-btn"
        >
          Retry
        </button>
      </main>
    );
  }

  const serverInterests = new Set(user.interests.split(",").filter(Boolean));
  const nameChanged = name !== user.name;
  const interestsChanged = !setsEqual(interests, serverInterests);
  const prefsChanged =
    format !== user.preferred_format || depth !== user.briefing_depth;
  const maxDepth = user.is_pro ? 25 : 10;

  return (
    <main className="max-w-2xl mx-auto px-4 py-8 space-y-10" data-testid="settings-page">
      <h1 className="text-2xl font-bold">Settings</h1>

      {saveError && (
        <div
          className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700"
          data-testid="save-error"
        >
          {saveError}
        </div>
      )}

      {/* Profile Section */}
      <section data-testid="profile-section">
        <h2 className="text-lg font-semibold mb-4">Profile</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              type="email"
              value={user.email}
              disabled
              className="w-full px-3 py-2 border border-gray-200 rounded-md bg-gray-50 text-gray-500 text-sm"
              data-testid="email-field"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              maxLength={100}
              className="w-full px-3 py-2 border border-gray-200 rounded-md text-sm focus:border-violet-500 focus:outline-none"
              data-testid="name-field"
            />
          </div>
          <SaveButton
            onClick={saveProfile}
            disabled={!nameChanged}
            isPending={updateUser.isPending}
          />
        </div>
      </section>

      {/* Interests Section */}
      <section data-testid="interests-section">
        <h2 className="text-lg font-semibold mb-1">Interests</h2>
        <p className="text-sm text-gray-500 mb-4">
          Select topics for your briefings
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          {CATEGORIES.map((cat) => (
            <InterestToggle
              key={cat}
              category={cat}
              selected={interests.has(cat)}
              onToggle={() => toggleInterest(cat)}
            />
          ))}
        </div>
        {!user.is_pro && (
          <p
            className="text-xs text-gray-400 mb-4"
            data-testid="tier-notice-interests"
          >
            Free tier: only your first selected category is used
          </p>
        )}
        <SaveButton
          onClick={saveInterests}
          disabled={!interestsChanged}
          isPending={updateUser.isPending}
        />
      </section>

      {/* Briefing Preferences Section */}
      <section data-testid="preferences-section">
        <h2 className="text-lg font-semibold mb-4">Briefing Preferences</h2>
        <div className="space-y-6">
          <FormatSelector
            value={format}
            onChange={setFormat}
            isPro={user.is_pro}
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Stories per briefing
            </label>
            <DepthSlider
              value={depth}
              onChange={setDepth}
              min={1}
              max={maxDepth}
            />
            {!user.is_pro && (
              <p
                className="text-xs text-gray-400 mt-2"
                data-testid="tier-notice-depth"
              >
                Free tier: max 10 stories. Upgrade for up to 25.
              </p>
            )}
          </div>
          <SaveButton
            onClick={savePreferences}
            disabled={!prefsChanged}
            isPending={updateUser.isPending}
          />
        </div>
      </section>

      {/* Subscription Section */}
      <section data-testid="subscription-section">
        <h2 className="text-lg font-semibold mb-4">Subscription</h2>
        <div className="space-y-4">
          {showSuccess && user.is_pro && (
            <SuccessBanner onDismiss={() => setShowSuccess(false)} />
          )}
          {showCancelled && (
            <div
              className="rounded-md bg-gray-50 border border-gray-200 p-3 text-sm text-gray-600"
              data-testid="cancelled-notice"
            >
              Upgrade cancelled. You can try again anytime.
            </div>
          )}
          {checkoutError && (
            <div
              className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700"
              data-testid="checkout-error"
            >
              {checkoutError}
            </div>
          )}
          <div className="flex items-center gap-3">
            <PlanBadge tier={user.is_pro ? "Pro" : "Free"} />
            <span className="text-sm text-gray-500">
              {user.is_pro
                ? "You have full access to all features"
                : "Upgrade to unlock all features"}
            </span>
            {user.is_pro && user.pro_since && (
              <span className="text-xs text-gray-400" data-testid="pro-since">
                Pro since {new Date(user.pro_since).toLocaleDateString("en-US", {
                  year: "numeric", month: "short", day: "numeric",
                })}
              </span>
            )}
          </div>
          {user.is_pro && user.pro_until && new Date(user.pro_until) > new Date() && (
            <GracePeriodWarning
              proUntil={user.pro_until}
              onUpdatePayment={handleManage}
              isLoading={portal.isPending}
            />
          )}
          {!user.is_pro && user.pro_until && (
            <div
              className="rounded-md bg-gray-50 border border-gray-200 p-3 text-sm text-gray-600"
              data-testid="resubscribe-notice"
            >
              Your Pro subscription ended on{" "}
              {new Date(user.pro_until).toLocaleDateString("en-US", {
                year: "numeric", month: "long", day: "numeric",
              })}.
            </div>
          )}
          {!user.is_pro && (
            <UpgradeCard
              onUpgrade={handleUpgrade}
              isLoading={checkout.isPending}
            />
          )}
          {user.is_pro && (
            <div data-testid="manage-section">
              <button
                onClick={handleManage}
                disabled={portal.isPending}
                className="px-4 py-2 text-sm font-medium rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                data-testid="manage-btn"
              >
                {portal.isPending ? "Opening..." : "Manage Subscription"}
              </button>
              <p className="text-xs text-gray-400 mt-1">
                Update payment method, view invoices, or cancel
              </p>
            </div>
          )}
          <FeatureComparison />
        </div>
      </section>

      {/* Danger Zone */}
      <section data-testid="danger-zone">
        <h2 className="text-lg font-semibold text-red-600 mb-4">
          Danger Zone
        </h2>
        <button
          disabled
          className="px-4 py-2 text-sm font-medium rounded-md border border-red-300 text-red-600 opacity-50 cursor-not-allowed"
          data-testid="delete-account-btn"
          title="Contact support to delete your account"
        >
          Delete Account
        </button>
      </section>
    </main>
  );
}

export { setsEqual };
