"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Topbar({ title }: { title: string }) {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15000,
    retry: false,
  });

  const online = !isError && data?.status === "ok";

  return (
    <header className="flex h-14 items-center justify-between border-b border-ink-700 bg-ink-900 px-6">
      <h1 className="font-display text-xl font-semibold tracking-tight">
        {title}
      </h1>
      <div className="flex items-center gap-2 text-xs text-paper-500">
        <span
          className={cn(
            "h-2 w-2 rounded-full",
            online ? "bg-accent-green" : "bg-signal-red",
          )}
        />
        <span className="uppercase tracking-label">
          {online ? "API online" : "API offline"}
        </span>
      </div>
    </header>
  );
}
