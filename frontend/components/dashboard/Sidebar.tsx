"use client";

import { useSession } from "next-auth/react";
import Link from "next/link";
import KeywordSidebar from "./KeywordSidebar";
import Button from "@/components/ui/Button";
import { useUserProfile } from "@/lib/hooks";

interface SidebarProps {
  onTriggerBriefing?: () => void;
  isTriggerPending?: boolean;
}

export default function Sidebar({
  onTriggerBriefing,
  isTriggerPending,
}: SidebarProps) {
  const { data: session } = useSession();
  const userId = (session?.user as Record<string, unknown> | undefined)
    ?.id as number | undefined;
  const { data: user } = useUserProfile(userId);
  const name =
    session?.user?.name ||
    session?.user?.email?.split("@")[0] ||
    "there";

  return (
    <aside
      className="hidden lg:flex lg:flex-col lg:w-[280px] border-r border-gray-200 p-4 gap-6"
      data-testid="sidebar"
    >
      <div>
        <p className="text-sm text-gray-500">Welcome back,</p>
        <p className="font-semibold" data-testid="user-greeting">
          {name}
        </p>
      </div>

      <KeywordSidebar />

      <div className="mt-auto space-y-2">
        {user && !user.is_pro && (
          <Link
            href="/pricing"
            className="block text-center text-sm text-violet-600 font-medium hover:underline"
            data-testid="upgrade-link"
          >
            Upgrade to Pro
          </Link>
        )}
        <Button
          onClick={onTriggerBriefing}
          disabled={isTriggerPending}
          fullWidth
        >
          {isTriggerPending ? "Generating..." : "Generate briefing"}
        </Button>
      </div>
    </aside>
  );
}
