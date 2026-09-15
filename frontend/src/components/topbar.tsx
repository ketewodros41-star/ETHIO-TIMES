"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Globe, Clock, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Topbar({ title }: { title: string }) {
  const [time, setTime] = useState({ eat: "", utc: "" });

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime({
        eat: now.toLocaleTimeString("en-US", {
          timeZone: "Africa/Addis_Ababa",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }),
        utc: now.toLocaleTimeString("en-US", {
          timeZone: "UTC",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        }),
      });
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

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
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-white/[0.08] bg-ink-950/80 backdrop-blur-md px-6 sticky top-0 z-30">
      {/* Title & Breadcrumb */}
      <div className="flex flex-col justify-center">
        <div className="flex items-center gap-2 text-[11px] font-mono text-paper-500 uppercase tracking-widest">
          <span>ETHIO-TIMES</span>
          <span>/</span>
          <span className="text-paper-400">Newsroom</span>
        </div>
        <h1 className="font-display text-lg font-bold tracking-tight text-paper-50 sm:text-xl">
          {title}
        </h1>
      </div>

      {/* Right Controls: Newsroom Clocks + API Health */}
      <div className="flex items-center gap-4 text-xs">
        {/* Live Newsroom Clock */}
        <div className="hidden md:flex items-center gap-3 border-r border-white/[0.08] pr-4 text-paper-400 font-mono text-[11.5px]">
          <div className="flex items-center gap-1.5" title="Addis Ababa Time (East Africa Time)">
            <Clock className="h-3.5 w-3.5 text-accent-green" />
            <span className="text-paper-100 font-semibold">{time.eat || "--:--:--"}</span>
            <span className="text-[10px] text-accent-green font-bold">EAT</span>
          </div>
          <div className="flex items-center gap-1 text-paper-500" title="Coordinated Universal Time">
            <span>({time.utc || "--:--"} UTC)</span>
          </div>
        </div>

        {/* API Health Indicator */}
        <div className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-ink-900/60 px-3 py-1 font-mono text-[11px]">
          <span className="relative flex h-2 w-2">
            {isOnline && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-green opacity-75"></span>
            )}
            <span
              className={cn(
                "relative inline-flex rounded-full h-2 w-2",
                isOnline && "bg-accent-green",
                isConnecting && "bg-yellow-400 animate-pulse",
                isOffline && "bg-signal-red"
              )}
            />
          </span>
          <span className="uppercase tracking-wider text-paper-300 font-medium">
            {isOnline ? "Network live" : isConnecting ? "Connecting…" : "Offline"}
          </span>
        </div>
      </div>
    </header>
  );
}


