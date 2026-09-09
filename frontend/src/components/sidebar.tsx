"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Layers,
  Newspaper,
  Radio,
  Image as ImageIcon,
  Settings,
} from "lucide-react";
import { Wordmark } from "@/components/wordmark";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/events", label: "Events", icon: Layers },
  { href: "/sources", label: "Sources", icon: Radio },
  { href: "/articles", label: "Articles", icon: Newspaper },
  { href: "/studio/templates", label: "Post Studio", icon: ImageIcon },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-ink-700 bg-ink-900">
      <div className="flex h-14 items-center border-b border-ink-700 px-4">
        <Wordmark />
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-card px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-ink-700 text-paper-50"
                  : "text-paper-500 hover:bg-ink-800 hover:text-paper-300",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-ink-700 p-3">
        <p className="text-[11px] uppercase tracking-label text-paper-500">
          News Intelligence
        </p>
        <p className="mt-1 text-[11px] text-ink-600">Phase 4 · trending</p>
      </div>
    </aside>
  );
}
