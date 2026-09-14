"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Topbar({ title }: { title: string }) {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15000,
    retry: 3,
    retryDelay: 2000,
  });

  const isHealthy = data?.status === "ok" || data?.status === "healthy";
  const isConnecting = isLoading && !data;
  const isOnline = !isError && isHealthy;
  const isOffline = isError || (!isLoading && !isHealthy);

  return (
    <header className="flex h-14 items-center justify-between border-b border-ink-700 bg-ink-900 px-6">
      <h1 className="font-display text-xl font-semibold tracking-tight">
        {title}
      </h1>
      <div className="flex items-center gap-2 text-xs text-paper-500">
        <span
          className={cn(
            "h-2 w-2 rounded-full",
            isOnline && "bg-accent-green",
            isConnecting && "bg-yellow-400 animate-pulse",
            isOffline && "bg-signal-red"
          )}
        />
        <span className="uppercase tracking-label">
          {isOnline ? "API online" : isConnecting ? "Connecting..." : "API offline"}
        </span>
      </div>
    </header>
  );
}

