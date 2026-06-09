"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Briefings", href: "/briefings" },
  { label: "Sources", href: "/sources" },
  { label: "Perception", href: "/perception" },
  { label: "Settings", href: "/settings" },
] as const;

const HIDDEN_ROUTES = ["/login", "/signup", "/check-email", "/auth-error", "/", "/pricing"];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

export default function MobileBottomNav() {
  const pathname = usePathname();
  const { status } = useSession();

  if (status !== "authenticated") return null;
  if (HIDDEN_ROUTES.some((r) => pathname === r)) return null;

  return (
    <nav
      className="fixed bottom-0 inset-x-0 z-50 border-t border-gray-200 bg-white lg:hidden"
      data-testid="mobile-bottom-nav"
    >
      <div className="flex items-center justify-around h-16">
        {NAV_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`flex-1 flex items-center justify-center h-full text-xs ${
                active
                  ? "text-violet-600 font-semibold border-t-2 border-violet-600"
                  : "text-gray-500 font-medium hover:text-gray-700"
              }`}
              data-testid={`bottom-nav-${item.label.toLowerCase()}`}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

export { NAV_ITEMS, HIDDEN_ROUTES, isActive };
