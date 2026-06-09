import Sidebar from "./Sidebar";

interface DashboardLayoutProps {
  children: React.ReactNode;
  onTriggerBriefing?: () => void;
  isTriggerPending?: boolean;
}

export default function DashboardLayout({
  children,
  onTriggerBriefing,
  isTriggerPending,
}: DashboardLayoutProps) {
  return (
    <div className="flex h-[calc(100dvh-4rem)] lg:h-screen">
      <Sidebar
        onTriggerBriefing={onTriggerBriefing}
        isTriggerPending={isTriggerPending}
      />
      <main className="flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  );
}
