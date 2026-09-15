import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(value?: string | null): string {
  if (!value) return "never";
  const normalized = typeof value === "string" ? value.replace(" ", "T") : value;
  const d = new Date(normalized).getTime();
  if (Number.isNaN(d)) return "never";
  const diff = Date.now() - d;
  if (diff < 0) return "just now";
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days}d ago`;
  if (days < 30) {
    const weeks = Math.round(days / 7);
    return `${weeks}w ago`;
  }
  const dateObj = new Date(normalized);
  const now = new Date();
  const sameYear = dateObj.getFullYear() === now.getFullYear();
  return dateObj.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    ...(sameYear ? {} : { year: "numeric" }),
  });
}
