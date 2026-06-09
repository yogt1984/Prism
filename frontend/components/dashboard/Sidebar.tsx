"use client";

import { useSession } from "next-auth/react";
import KeywordSidebar from "./KeywordSidebar";
import Button from "@/components/ui/Button";

interface SidebarProps {
  onTriggerBriefing?: () => void;
  isTriggerPending?: boolean;
}

export default function Sidebar({
  onTriggerBriefing,
  isTriggerPending,
}: SidebarProps) {
  const { data: session } = useSession();
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
