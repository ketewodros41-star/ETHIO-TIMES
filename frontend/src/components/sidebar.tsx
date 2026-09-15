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
  Send,
  Zap,
  ShieldCheck,
  Activity,
} from "lucide-react";
import { Wordmark } from "@/components/wordmark";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    title: "Intelligence Desk",
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboard },
      { href: "/events", label: "Events Feed", icon: Layers, badge: "Live" },
      { href: "/trends", label: "Trend Radar", icon: Zap },
      { href: "/verification", label: "Fact-Check Desk", icon: ShieldCheck },
    ],
  },
  {
    title: "Publishing & Media",
    items: [
      { href: "/posts", label: "Telegram Posts", icon: Send },
      { href: "/studio/templates", label: "Post Studio", icon: ImageIcon },
    ],
  },
  {
    title: "Feeds & Ingestion",
    items: [
      { href: "/sources", label: "News Sources", icon: Radio },
      { href: "/articles", label: "Articles Stream", icon: Newspaper },
    ],
  },
  {
    title: "Administration",
    items: [
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-white/[0.08] bg-ink-950/95 backdrop-blur-md select-none">
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between border-b border-white/[0.08] px-4">
        <Wordmark />
        <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-green/10 border border-accent-green/30 px-2 py-0.5 text-[10px] font-mono font-semibold text-accent-green">
          <span className="h-1.5 w-1.5 rounded-full bg-accent-green animate-pulse" />
          LIVE
        </span>
      </div>

      {/* Nav Sections */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {SECTIONS.map((section) => (
          <div key={section.title} className="space-y-1">
            <p className="px-3 text-[10px] font-mono font-semibold uppercase tracking-widest text-paper-500/80">
              {section.title}
            </p>
            <div className="space-y-0.5 pt-1">
              {section.items.map(({ href, label, icon: Icon, badge }) => {
                const active =
                  href === "/" ? pathname === "/" : pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={cn(
                      "group relative flex items-center justify-between rounded-card px-3 py-2 text-xs font-medium transition-all duration-150",
                      active
                        ? "bg-white/[0.08] text-paper-50 font-semibold shadow-xs"
                        : "text-paper-400 hover:bg-white/[0.04] hover:text-paper-100",
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r-full bg-accent-green shadow-[0_0_8px_rgba(31,163,90,0.8)]" />
                    )}
                    <div className="flex items-center gap-2.5">
                      <Icon
                        className={cn(
                          "h-4 w-4 transition-colors",
                          active
                            ? "text-accent-green"
                            : "text-paper-500 group-hover:text-paper-300",
                        )}
                      />
                      <span>{label}</span>
                    </div>
                    {badge && (
                      <span
                        className={cn(
                          "rounded-full px-1.5 py-0.2 text-[9.5px] font-mono font-semibold",
                          active
                            ? "bg-accent-green/20 text-accent-green"
                            : "bg-ink-750 text-paper-400",
                        )}
                      >
                        {badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* System Status Footer */}
      <div className="border-t border-white/[0.08] p-3.5 bg-ink-900/40">
        <div className="flex items-center justify-between text-[11px] text-paper-400 font-mono">
          <span className="inline-flex items-center gap-1.5">
            <Activity className="h-3 w-3 text-accent-green animate-pulse" />
            <span>Autonomous Engine</span>
          </span>
          <span className="text-[10px] text-paper-500">v2.4-pro</span>
        </div>
      </div>
    </aside>
  );
}

