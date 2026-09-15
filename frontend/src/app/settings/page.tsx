"use client";

import { useEffect, useState, useCallback } from "react";
import { PageShell } from "@/components/page-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_BASE, api } from "@/lib/api";
import type { BucketContentFilter, PublishingSettings, TelegramPublishingSettings } from "@/lib/types";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-ink-800 py-2 last:border-0">
      <span className="text-sm text-paper-500">{label}</span>
      <span className="font-mono text-sm text-paper-300" suppressHydrationWarning>
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Topic categories available for filtering
// ---------------------------------------------------------------------------
const CATEGORIES = [
  "Politics",
  "Business",
  "Sports",
  "Football",
  "Crime",
  "Society",
  "World Affairs",
  "Conflict",
  "Science",
  "Technology",
  "Entertainment",
  "Health",
  "Economy",
  "Education",
  "Environment",
  "Culture",
] as const;

type Category = (typeof CATEGORIES)[number];

interface BucketFilterEditorProps {
  bucket: "ethiopia" | "international";
  label: string;
  description: string;
  filter: BucketContentFilter;
  onChange: (bucket: "ethiopia" | "international", updated: BucketContentFilter) => void;
}

function BucketFilterEditor({
  bucket,
  label,
  description,
  filter,
  onChange,
}: BucketFilterEditorProps) {
  const [kwInput, setKwInput] = useState("");
  const [blockedKwInput, setBlockedKwInput] = useState("");

  const toggleCategory = (cat: string, list: "allowed" | "blocked") => {
    const field = list === "allowed" ? "allowed_categories" : "blocked_categories";
    const current = filter[field];
    const lower = cat.toLowerCase();
    const already = current.some((c) => c.toLowerCase() === lower);
    onChange(bucket, {
      ...filter,
      [field]: already ? current.filter((c) => c.toLowerCase() !== lower) : [...current, cat],
    });
  };

  const addKeyword = (list: "allowed" | "blocked") => {
    const raw = list === "allowed" ? kwInput.trim() : blockedKwInput.trim();
    if (!raw) return;
    const field = list === "allowed" ? "allowed_keywords" : "blocked_keywords";
    const lower = raw.toLowerCase();
    if (!filter[field].some((k) => k.toLowerCase() === lower)) {
      onChange(bucket, { ...filter, [field]: [...filter[field], raw] });
    }
    if (list === "allowed") setKwInput("");
    else setBlockedKwInput("");
  };

  const removeKeyword = (kw: string, list: "allowed" | "blocked") => {
    const field = list === "allowed" ? "allowed_keywords" : "blocked_keywords";
    const lower = kw.toLowerCase();
    onChange(bucket, { ...filter, [field]: filter[field].filter((k) => k.toLowerCase() !== lower) });
  };

  const isAllowed = (cat: string) =>
    filter.allowed_categories.some((c) => c.toLowerCase() === cat.toLowerCase());
  const isBlocked = (cat: string) =>
    filter.blocked_categories.some((c) => c.toLowerCase() === cat.toLowerCase());

  return (
    <div className="space-y-4">
      <p className="text-sm text-paper-400">{description}</p>

      {/* Category whitelist */}
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-paper-500">
          Allowed categories{" "}
          <span className="normal-case font-normal text-paper-600">
            (empty = allow all)
          </span>
        </p>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((cat) => {
            const allowed = isAllowed(cat);
            const blocked = isBlocked(cat);
            return (
              <button
                key={cat}
                type="button"
                onClick={() => toggleCategory(cat, "allowed")}
                disabled={blocked}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-all border ${
                  allowed
                    ? "border-accent-green bg-accent-green/20 text-accent-green"
                    : blocked
                    ? "border-red-700/40 bg-red-900/10 text-red-700 cursor-not-allowed opacity-50"
                    : "border-ink-700 bg-ink-900 text-paper-400 hover:border-accent-green/50 hover:text-accent-green"
                }`}
              >
                {allowed ? "✓ " : ""}{cat}
              </button>
            );
          })}
        </div>
      </div>

      {/* Category blocklist */}
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-paper-500">
          Blocked categories{" "}
          <span className="normal-case font-normal text-paper-600">
            (always excluded, overrides whitelist)
          </span>
        </p>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((cat) => {
            const blocked = isBlocked(cat);
            const allowed = isAllowed(cat);
            return (
              <button
                key={cat}
                type="button"
                onClick={() => toggleCategory(cat, "blocked")}
                disabled={allowed}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-all border ${
                  blocked
                    ? "border-red-500 bg-red-500/20 text-red-400"
                    : allowed
                    ? "border-ink-700/40 bg-ink-900/10 text-paper-600 cursor-not-allowed opacity-50"
                    : "border-ink-700 bg-ink-900 text-paper-400 hover:border-red-500/50 hover:text-red-400"
                }`}
              >
                {blocked ? "✗ " : ""}{cat}
              </button>
            );
          })}
        </div>
      </div>

      {/* Allowed keywords */}
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-paper-500">
          Required keywords{" "}
          <span className="normal-case font-normal text-paper-600">
            (empty = no restriction; if set, post must contain at least one)
          </span>
        </p>
        <div className="flex gap-2 mb-2">
          <Input
            placeholder="e.g. election, ምርጫ…"
            value={kwInput}
            onChange={(e) => setKwInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addKeyword("allowed")}
            className="h-8 text-sm max-w-xs font-sans"
            dir="auto"
          />
          <Button size="sm" variant="outline" onClick={() => addKeyword("allowed")}>
            Add
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {filter.allowed_keywords.map((kw) => (
            <span
              key={kw}
              className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/40 bg-sky-500/10 px-2.5 py-1 text-xs text-sky-300 font-sans break-keep leading-tight"
              dir="auto"
            >
              <span>{kw}</span>
              <button
                type="button"
                onClick={() => removeKeyword(kw, "allowed")}
                className="ml-0.5 text-sky-400 hover:text-sky-200 transition-colors focus:outline-none"
                aria-label={`Remove ${kw}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Blocked keywords */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-paper-500">
            Blocked keywords{" "}
            <span className="normal-case font-normal text-paper-600">
              (posts containing these are excluded)
            </span>
          </p>
          <button
            type="button"
            onClick={() => {
              const existingLower = new Set(filter.blocked_keywords.map((k) => k.toLowerCase()));
              const missing = DEFAULT_BLOCKED_KEYWORDS.filter((k) => !existingLower.has(k.toLowerCase()));
              if (missing.length > 0) {
                onChange(bucket, {
                  ...filter,
                  blocked_keywords: [...filter.blocked_keywords, ...missing],
                });
              }
            }}
            className="text-[11px] text-paper-400 hover:text-paper-200 underline underline-offset-2 transition-colors cursor-pointer"
          >
            + Add standard ad/PR presets
          </button>
        </div>
        <div className="flex gap-2 mb-2">
          <Input
            placeholder="e.g. sponsored, ማስታወቂያ, ቴሌብር…"
            value={blockedKwInput}
            onChange={(e) => setBlockedKwInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addKeyword("blocked")}
            className="h-8 text-sm max-w-xs font-sans"
            dir="auto"
          />
          <Button size="sm" variant="outline" onClick={() => addKeyword("blocked")}>
            Add
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {filter.blocked_keywords.map((kw) => (
            <span
              key={kw}
              className="inline-flex items-center gap-1.5 rounded-full border border-red-500/40 bg-red-500/10 px-2.5 py-1 text-xs text-red-300 font-sans break-keep leading-tight"
              dir="auto"
            >
              <span>{kw}</span>
              <button
                type="button"
                onClick={() => removeKeyword(kw, "blocked")}
                className="ml-0.5 text-red-400 hover:text-red-200 transition-colors focus:outline-none"
                aria-label={`Remove ${kw}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Default blocked keywords & empty filter for a bucket
// ---------------------------------------------------------------------------
const DEFAULT_BLOCKED_KEYWORDS: string[] = [
  "sponsored",
  "advertisement",
  "advertorial",
  "press release",
  "partner content",
  "ad feature",
  "promoted",
  "ማስታወቂያ",
  "ማስተዋወቂያ",
  "ስፖንሰር",
  "የስፖንሰር",
  "ስፖንሰር የተደረገ",
  "የተከፈለበት",
  "የንግድ ማስታወቂያ",
  "ጋዜጣዊ መግለጫ",
  "አጋር ይዘት",
  "ኢትዮ ቴሌኮም",
  "ቴሌብር",
  "ልዩ ቅናሽ",
];

function emptyFilter(): BucketContentFilter {
  return {
    allowed_categories: [],
    blocked_categories: [],
    allowed_keywords: [],
    blocked_keywords: [...DEFAULT_BLOCKED_KEYWORDS],
  };
}

export default function SettingsPage() {
  const [mounted, setMounted] = useState(false);
  const [settings, setSettings] = useState<PublishingSettings | null>(null);
  const [postsPerDay, setPostsPerDay] = useState("1");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [telegram, setTelegram] = useState<TelegramPublishingSettings | null>(null);
  const [telegramTotal, setTelegramTotal] = useState("5");
  const [ethiopiaQuota, setEthiopiaQuota] = useState("3");
  const [internationalQuota, setInternationalQuota] = useState("2");
  const [telegramSaving, setTelegramSaving] = useState(false);
  const [telegramMessage, setTelegramMessage] = useState("");
  const [testingBroadcast, setTestingBroadcast] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    headline?: string | null;
    telegram_message_id?: string | null;
  } | null>(null);

  // Content filters state
  const [ethiopiaFilter, setEthiopiaFilter] = useState<BucketContentFilter>(emptyFilter());
  const [internationalFilter, setInternationalFilter] = useState<BucketContentFilter>(emptyFilter());
  const [filterSaving, setFilterSaving] = useState(false);
  const [filterMessage, setFilterMessage] = useState<{ text: string; success: boolean } | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    api
      .getPublishingSettings()
      .then((v) => {
        setSettings(v);
        setPostsPerDay(String(v.posts_per_day));
      })
      .catch((e) => setMessage(e.message));
  }, []);

  useEffect(() => {
    api
      .getTelegramPublishingSettings()
      .then((v) => {
        setTelegram(v);
        setTelegramTotal(String(v.posts_per_day));
        setEthiopiaQuota(String(v.ethiopia_posts_per_day));
        setInternationalQuota(String(v.international_posts_per_day));
        // Initialise filter editors from saved settings
        if (v.content_filters?.ethiopia) {
          setEthiopiaFilter(v.content_filters.ethiopia);
        }
        if (v.content_filters?.international) {
          setInternationalFilter(v.content_filters.international);
        }
      })
      .catch((e) => setTelegramMessage(e.message));
  }, []);

  const save = async () => {
    const posts = Number(postsPerDay);
    if (!Number.isInteger(posts) || posts < 0 || posts > 24) {
      setMessage("Choose a whole number from 0 to 24.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const value = await api.updatePublishingSettings({ posts_per_day: posts });
      setSettings(value);
      setPostsPerDay(String(value.posts_per_day));
      setMessage("Daily publishing limit saved.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not save settings.");
    } finally {
      setSaving(false);
    }
  };

  const handleTotalChange = (val: string) => {
    setTelegramTotal(val);
    const num = Number(val);
    if (Number.isInteger(num) && num >= 0 && num <= 24) {
      const et = Math.round(num * 0.6);
      const intl = num - et;
      setEthiopiaQuota(String(et));
      setInternationalQuota(String(intl));
    }
  };

  const handleEthiopiaChange = (val: string) => {
    setEthiopiaQuota(val);
    const et = Number(val);
    const intl = Number(internationalQuota);
    if (Number.isInteger(et) && Number.isInteger(intl) && et >= 0) {
      setTelegramTotal(String(et + intl));
    }
  };

  const handleInternationalChange = (val: string) => {
    setInternationalQuota(val);
    const intl = Number(val);
    const et = Number(ethiopiaQuota);
    if (Number.isInteger(intl) && Number.isInteger(et) && intl >= 0) {
      setTelegramTotal(String(et + intl));
    }
  };

  const saveTelegramMix = async () => {
    const total = Number(telegramTotal);
    const et = Number(ethiopiaQuota);
    const intl = Number(internationalQuota);
    if (![total, et, intl].every(Number.isInteger) || total < 0 || total > 24 || et < 0 || intl < 0 || et + intl !== total) {
      setTelegramMessage("Telegram quotas must be whole numbers (0–24) and Ethiopia + International must equal Total.");
      return;
    }
    setTelegramSaving(true);
    setTelegramMessage("");
    try {
      const v = await api.updateTelegramPublishingSettings({
        posts_per_day: total,
        ethiopia_posts_per_day: et,
        international_posts_per_day: intl,
      });
      setTelegram(v);
      setTelegramTotal(String(v.posts_per_day));
      setEthiopiaQuota(String(v.ethiopia_posts_per_day));
      setInternationalQuota(String(v.international_posts_per_day));
      setTelegramMessage("Telegram daily mix saved successfully.");
    } catch (e) {
      setTelegramMessage(e instanceof Error ? e.message : "Could not save Telegram settings.");
    } finally {
      setTelegramSaving(false);
    }
  };

  const handleFilterChange = useCallback(
    (bucket: "ethiopia" | "international", updated: BucketContentFilter) => {
      if (bucket === "ethiopia") setEthiopiaFilter(updated);
      else setInternationalFilter(updated);
    },
    [],
  );

  const saveContentFilters = async () => {
    setFilterSaving(true);
    setFilterMessage(null);
    try {
      const v = await api.updateContentFilters({
        ethiopia: ethiopiaFilter,
        international: internationalFilter,
      });
      setTelegram(v);
      if (v.content_filters?.ethiopia) setEthiopiaFilter(v.content_filters.ethiopia);
      if (v.content_filters?.international) setInternationalFilter(v.content_filters.international);
      setFilterMessage({ text: "Content filters saved successfully.", success: true });
    } catch (e) {
      setFilterMessage({
        text: e instanceof Error ? e.message : "Could not save content filters.",
        success: false,
      });
    } finally {
      setFilterSaving(false);
    }
  };

  return (
    <PageShell title="Settings">
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-accent-green/30">
          <CardHeader>
            <CardTitle>Publishing automation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-paper-300">
              Set the maximum number of posts the scheduler may create in one Addis Ababa day. Manual posts are never blocked by this limit.
            </p>
            <label className="block text-xs font-mono uppercase tracking-label text-paper-500" htmlFor="posts-per-day">
              Posts per day
            </label>
            <div className="flex max-w-sm gap-2">
              <Input id="posts-per-day" type="number" min="0" max="24" value={postsPerDay} onChange={(e) => setPostsPerDay(e.target.value)} />
              <Button onClick={save} disabled={saving}>
                {saving ? "Saving…" : "Save limit"}
              </Button>
            </div>
            <p className="text-xs text-paper-500">0 pauses automation. Allowed range: 0–24 posts/day.</p>
            <Row label="Timezone" value={settings?.timezone || "Africa/Addis_Ababa"} />
            <Row label="Automation" value={<Badge variant="muted">scheduled rollout</Badge>} />
            {message && (
              <p role="status" className="text-sm text-accent-green">
                {message}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Environment</CardTitle>
          </CardHeader>
          <CardContent>
            <Row
              label="Backend API URL"
              value={process.env.NEXT_PUBLIC_API_BASE_URL || "https://ethiotimes-backend.onrender.com"}
            />
            <Row label="Mode" value="Manual + controlled automation" />
          </CardContent>
        </Card>
        <Card className="border-sky-500/30">
          <CardHeader>
            <CardTitle>Telegram channel automation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-paper-300">
              {`Plans ${telegram?.ethiopia_posts_per_day ?? 3} Ethiopia posts in Amharic and ${telegram?.international_posts_per_day ?? 2} international posts in English (${telegram?.posts_per_day ?? 5} total/day). Telegram cards and delivery are independent from Instagram.`}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant={telegram?.enabled ? "default" : "outline"}
                onClick={async () => {
                  try {
                    const v = await api.updateTelegramPublishingSettings({ enabled: !telegram?.enabled });
                    setTelegram(v);
                    setTelegramMessage(v.enabled ? "Telegram automation enabled." : "Telegram automation paused.");
                  } catch (e) {
                    setTelegramMessage(e instanceof Error ? e.message : "Failed to toggle automation.");
                  }
                }}
                disabled={!telegram?.bot_configured && !telegram?.dry_run}
              >
                {telegram?.enabled ? "Automation enabled" : "Enable Telegram"}
              </Button>
              <Button
                variant="outline"
                onClick={async () => {
                  try {
                    const nextDryRun = !telegram?.dry_run;
                    if (!nextDryRun && !telegram?.bot_configured) {
                      setTelegramMessage("Bot token is not configured. Live mode requires TELEGRAM_BOT_TOKEN.");
                      return;
                    }
                    const v = await api.updateTelegramPublishingSettings({ dry_run: nextDryRun });
                    setTelegram(v);
                    setTelegramMessage(v.dry_run ? "Switched to Dry-run mode." : "Switched to Live publishing mode.");
                  } catch (e) {
                    setTelegramMessage(e instanceof Error ? e.message : "Failed to toggle mode.");
                  }
                }}
              >
                {telegram ? (telegram.dry_run ? "Switch to Live mode" : "Switch to Dry-run") : "Mode"}
              </Button>
              <Button
                variant="subtle"
                onClick={async () => {
                  setTestingBroadcast(true);
                  setTestResult(null);
                  try {
                    const res = await api.testTelegramPost();
                    setTestResult({
                      success: res.success,
                      message: res.message,
                      headline: res.headline,
                      telegram_message_id: res.telegram_message_id,
                    });
                  } catch (e) {
                    setTestResult({
                      success: false,
                      message: e instanceof Error ? e.message : "Failed to dispatch test broadcast.",
                    });
                  } finally {
                    setTestingBroadcast(false);
                  }
                }}
                disabled={testingBroadcast || !telegram?.bot_configured}
              >
                {testingBroadcast ? "Broadcasting…" : "Test Broadcast Now"}
              </Button>
            </div>
            {testResult && (
              <div
                role="status"
                className={`rounded-card border p-3 text-sm ${
                  testResult.success
                    ? "border-accent-green/40 bg-accent-green/10 text-accent-green"
                    : "border-red-500/40 bg-red-500/10 text-red-400"
                }`}
              >
                <div className="font-semibold">{testResult.message}</div>
                {testResult.headline && (
                  <div className="mt-1 text-xs text-paper-300">
                    <span className="text-paper-500">Headline:</span> {testResult.headline}
                  </div>
                )}
                {testResult.telegram_message_id && (
                  <div className="mt-0.5 text-xs text-paper-300">
                    <span className="text-paper-500">Telegram Msg ID:</span> {testResult.telegram_message_id}
                  </div>
                )}
              </div>
            )}
            <div className="grid grid-cols-3 gap-2">
              <label className="text-xs text-paper-400">
                Total
                <Input type="number" min="0" max="24" value={telegramTotal} onChange={(e) => handleTotalChange(e.target.value)} />
              </label>
              <label className="text-xs text-paper-400">
                Ethiopia
                <Input type="number" min="0" max="24" value={ethiopiaQuota} onChange={(e) => handleEthiopiaChange(e.target.value)} />
              </label>
              <label className="text-xs text-paper-400">
                International
                <Input type="number" min="0" max="24" value={internationalQuota} onChange={(e) => handleInternationalChange(e.target.value)} />
              </label>
            </div>
            <Button size="sm" onClick={saveTelegramMix} disabled={telegramSaving}>
              {telegramSaving ? "Saving…" : "Save Telegram mix"}
            </Button>
            {telegramMessage && (
              <p role="status" className="text-sm text-sky-400">
                {telegramMessage}
              </p>
            )}
            <Row
              label="Delivery mode"
              value={
                <Badge variant={telegram?.dry_run ? "gold" : "green"}>
                  {telegram?.dry_run ? "Dry-run (simulated)" : "Live delivery"}
                </Badge>
              }
            />
            <Row label="Channel" value={telegram?.channel_username || "@Ethiopantimes"} />
            <Row
              label="Bot token"
              value={<Badge variant={telegram?.bot_configured ? "green" : "gold"}>{telegram?.bot_configured ? "configured" : "missing"}</Badge>}
            />
            <Row
              label="Daily mix"
              value={`${telegram?.ethiopia_posts_per_day ?? 3} Ethiopia / ${telegram?.international_posts_per_day ?? 2} international`}
            />
            <Row
              label="Posting hours"
              value={(telegram?.posting_hours || [8, 11, 14, 17, 20]).map((h) => `${h}:00`).join(", ")}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Secrets &amp; credentials</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-paper-300">Secret values are never displayed in the dashboard; they remain environment variables.</p>
            <Row label="INSTAGRAM_ACCESS_TOKEN" value={<Badge variant="muted">env</Badge>} />
            <Row label="AGENT_ROUTER" value={<Badge variant="muted">env</Badge>} />
          </CardContent>
        </Card>
      </div>

      {/* ─── Content Filters Panel ────────────────────────────────────────────── */}
      <div className="mt-6">
        <Card className="border-amber-500/30">
          <CardHeader>
            <CardTitle>
              Content filters
              <span className="ml-2 text-sm font-normal text-paper-500">
                — Control what gets posted on Telegram per channel
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-8">
            <p className="text-sm text-paper-300">
              Fine-tune which topics appear in each Telegram channel. Blocked keywords
              (including <span className="font-mono text-red-400 text-xs">sponsored</span>,{" "}
              <span className="font-mono text-red-400 text-xs">advertisement</span>, and similar) are
              enforced automatically even without explicit configuration. Changes take effect on the next
              automated posting cycle (~10 min).
            </p>

            {/* Ad/sponsor filter notice */}
            <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-xs text-red-400">
              <span className="font-semibold">🛡 Ad/Sponsored filter is always active.</span>{" "}
              Events containing signals like &quot;sponsored&quot;, &quot;advertisement&quot;,
              &quot;advertorial&quot;, &quot;press release&quot;, &quot;Ethio Telecom&quot; etc. are
              automatically rejected before reaching these filters.
            </div>

            {/* Ethiopia bucket */}
            <div className="space-y-3">
              <h3 className="text-base font-semibold text-paper-200 flex items-center gap-2">
                🇪🇹 Ethiopia Posts
                <Badge variant="muted">Amharic</Badge>
              </h3>
              <BucketFilterEditor
                bucket="ethiopia"
                label="Ethiopia"
                description="Rules applied when selecting Ethiopian news for the Amharic Telegram channel."
                filter={ethiopiaFilter}
                onChange={handleFilterChange}
              />
            </div>

            <div className="border-t border-ink-800" />

            {/* International bucket */}
            <div className="space-y-3">
              <h3 className="text-base font-semibold text-paper-200 flex items-center gap-2">
                🌍 International Posts
                <Badge variant="muted">English</Badge>
              </h3>
              <BucketFilterEditor
                bucket="international"
                label="International"
                description="Rules applied when selecting international news for the English Telegram channel."
                filter={internationalFilter}
                onChange={handleFilterChange}
              />
            </div>

            {/* Save button + toast */}
            <div className="flex items-center gap-4">
              <Button onClick={saveContentFilters} disabled={filterSaving}>
                {filterSaving ? "Saving filters…" : "Save content filters"}
              </Button>
              {filterMessage && (
                <p
                  role="status"
                  className={`text-sm ${filterMessage.success ? "text-accent-green" : "text-red-400"}`}
                >
                  {filterMessage.text}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}
