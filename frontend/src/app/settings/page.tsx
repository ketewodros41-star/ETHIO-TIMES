"use client";

import { useEffect, useState, useCallback } from "react";
import { PageShell } from "@/components/page-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { BucketContentFilter, PublishingSettings, TelegramPublishingSettings } from "@/lib/types";
import {
  Sliders,
  Layers,
  ShieldCheck,
  Check,
  X,
  Send,
  RefreshCw,
  Clock,
  Globe,
  Building2,
  Briefcase,
  Trophy,
  Flame,
  Cpu,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Settings as SettingsIcon,
  Radio,
} from "lucide-react";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-ink-800 py-2.5 last:border-0">
      <span className="text-xs text-paper-500">{label}</span>
      <span className="font-mono text-xs text-paper-300" suppressHydrationWarning>
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rich News Beat Definitions with Icons and Context
// ---------------------------------------------------------------------------
interface BeatDefinition {
  id: string;
  name: string;
  icon: React.ReactNode;
  description: string;
  categoryKeys: string[];
}

const BEAT_DEFINITIONS: BeatDefinition[] = [
  {
    id: "Politics",
    name: "Politics & Governance",
    icon: <Building2 className="h-4 w-4 text-amber-400" />,
    description: "Elections, parliamentary bills, ministerial announcements, diplomacy, and official state policies.",
    categoryKeys: ["politics", "governance", "election", "parliament", "government"],
  },
  {
    id: "Business",
    name: "Business & Economy",
    icon: <Briefcase className="h-4 w-4 text-emerald-400" />,
    description: "Banking, trade, inflation, exchange rates, foreign investments, and financial markets.",
    categoryKeys: ["business", "economy", "finance", "banking", "market", "trade"],
  },
  {
    id: "Sports",
    name: "Sports & Football",
    icon: <Trophy className="h-4 w-4 text-sky-400" />,
    description: "Premier League, Champions League, African football, national tournaments, and athletics.",
    categoryKeys: ["sports", "football", "soccer", "athletics", "olympic", "marathon"],
  },
  {
    id: "World Affairs",
    name: "World Affairs & Geopolitics",
    icon: <Globe className="h-4 w-4 text-blue-400" />,
    description: "Global diplomacy, UN summits, bilateral agreements, international relations, and major summits.",
    categoryKeys: ["world affairs", "world", "international", "diplomacy", "global"],
  },
  {
    id: "Conflict",
    name: "Conflict & Security",
    icon: <Flame className="h-4 w-4 text-rose-400" />,
    description: "Peace accords, defense updates, regional security, and humanitarian developments.",
    categoryKeys: ["conflict", "security", "military", "defense", "peace", "war"],
  },
  {
    id: "Technology",
    name: "Technology & Innovation",
    icon: <Cpu className="h-4 w-4 text-purple-400" />,
    description: "AI, telecommunications, digital infrastructure, mobile money, and tech startups.",
    categoryKeys: ["technology", "tech", "telecom", "innovation", "digital", "ai"],
  },
  {
    id: "Culture",
    name: "Culture & Society",
    icon: <Sparkles className="h-4 w-4 text-yellow-400" />,
    description: "Arts, cultural heritage, diaspora communities, education, and social trends.",
    categoryKeys: ["culture", "society", "art", "heritage", "entertainment", "diaspora"],
  },
  {
    id: "Breaking",
    name: "Breaking News Priority",
    icon: <AlertCircle className="h-4 w-4 text-red-400" />,
    description: "Urgent breaking alerts and fast-moving developing events requiring immediate coverage.",
    categoryKeys: ["breaking", "urgent", "alert"],
  },
];

const DEFAULT_BLOCKED_TERMS = [
  "sponsored", "advertisement", "advertorial", "press release", "partner content",
  "ማስታወቂያ", "ማስተዋወቂያ", "ስፖንሰር", "የስፖንሰር", "የተከፈለበት", "የንግድ ማስታወቂያ",
  "ጋዜጣዊ መግለጫ", "አጋር ይዘት", "ኢትዮ ቴሌኮም", "ቴሌብር", "ልዩ ቅናሽ"
];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"mix" | "beats" | "shield" | "system">("mix");
  const [activeStream, setActiveStream] = useState<"ethiopia" | "international">("ethiopia");

  const [settings, setSettings] = useState<PublishingSettings | null>(null);
  const [telegram, setTelegram] = useState<TelegramPublishingSettings | null>(null);

  // Quota & timing states
  const [telegramTotal, setTelegramTotal] = useState("5");
  const [ethiopiaQuota, setEthiopiaQuota] = useState("3");
  const [internationalQuota, setInternationalQuota] = useState("2");
  const [freshnessHours, setFreshnessHours] = useState("36");
  const [bypassBreaking, setBypassBreaking] = useState(true);

  // Content filters
  const [ethiopiaFilter, setEthiopiaFilter] = useState<BucketContentFilter>({
    allowed_categories: [],
    blocked_categories: [],
    allowed_keywords: [],
    blocked_keywords: [...DEFAULT_BLOCKED_TERMS],
  });
  const [internationalFilter, setInternationalFilter] = useState<BucketContentFilter>({
    allowed_categories: [],
    blocked_categories: [],
    allowed_keywords: [],
    blocked_keywords: [...DEFAULT_BLOCKED_TERMS],
  });

  // UI state
  const [isSaving, setIsSaving] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ text: string; success: boolean } | null>(null);
  const [testingBroadcast, setTestingBroadcast] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    headline?: string | null;
    telegram_message_id?: string | null;
  } | null>(null);

  // Keyword inputs
  const [newKeywordInput, setNewKeywordInput] = useState("");
  const [newBlockedKwInput, setNewBlockedKwInput] = useState("");

  useEffect(() => {
    api.getPublishingSettings().then(setSettings).catch(() => {});
    api.getTelegramPublishingSettings().then((v) => {
      setTelegram(v);
      setTelegramTotal(String(v.posts_per_day));
      setEthiopiaQuota(String(v.ethiopia_posts_per_day));
      setInternationalQuota(String(v.international_posts_per_day));
      if (v.freshness_hours !== undefined) setFreshnessHours(String(v.freshness_hours));
      if (v.bypass_freshness_for_breaking !== undefined) {
        setBypassBreaking(Boolean(v.bypass_freshness_for_breaking));
      }
      if (v.content_filters?.ethiopia) setEthiopiaFilter(v.content_filters.ethiopia);
      if (v.content_filters?.international) setInternationalFilter(v.content_filters.international);
    }).catch((e) => {
      setToastMessage({ text: e instanceof Error ? e.message : "Failed to load settings.", success: false });
    });
  }, []);

  // Ratio calculations
  const totalNum = Number(telegramTotal) || 0;
  const etNum = Number(ethiopiaQuota) || 0;
  const intlNum = Number(internationalQuota) || 0;
  const etPct = totalNum > 0 ? Math.round((etNum / totalNum) * 100) : 60;
  const intlPct = totalNum > 0 ? 100 - etPct : 40;

  // Preset Ratio Applier
  const applyPreset = (etFraction: number) => {
    const total = Math.max(1, totalNum || 5);
    const et = Math.round(total * etFraction);
    const intl = total - et;
    setEthiopiaQuota(String(et));
    setInternationalQuota(String(intl));
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

  // Beat toggle helpers for active stream
  const currentFilter = activeStream === "ethiopia" ? ethiopiaFilter : internationalFilter;
  const setCurrentFilter = activeStream === "ethiopia" ? setEthiopiaFilter : setInternationalFilter;

  const isBeatWhitelisted = (beatId: string) =>
    currentFilter.allowed_categories.some((c) => c.toLowerCase() === beatId.toLowerCase());

  const isBeatBlocked = (beatId: string) =>
    currentFilter.blocked_categories.some((c) => c.toLowerCase() === beatId.toLowerCase());

  const toggleBeatAllow = (beatId: string) => {
    const lower = beatId.toLowerCase();
    const alreadyAllowed = currentFilter.allowed_categories.some((c) => c.toLowerCase() === lower);
    if (alreadyAllowed) {
      setCurrentFilter({
        ...currentFilter,
        allowed_categories: currentFilter.allowed_categories.filter((c) => c.toLowerCase() !== lower),
      });
    } else {
      setCurrentFilter({
        ...currentFilter,
        allowed_categories: [...currentFilter.allowed_categories, beatId],
        blocked_categories: currentFilter.blocked_categories.filter((c) => c.toLowerCase() !== lower),
      });
    }
  };

  const toggleBeatBlock = (beatId: string) => {
    const lower = beatId.toLowerCase();
    const alreadyBlocked = currentFilter.blocked_categories.some((c) => c.toLowerCase() === lower);
    if (alreadyBlocked) {
      setCurrentFilter({
        ...currentFilter,
        blocked_categories: currentFilter.blocked_categories.filter((c) => c.toLowerCase() !== lower),
      });
    } else {
      setCurrentFilter({
        ...currentFilter,
        blocked_categories: [...currentFilter.blocked_categories, beatId],
        allowed_categories: currentFilter.allowed_categories.filter((c) => c.toLowerCase() !== lower),
      });
    }
  };

  const resetAllBeats = () => {
    setCurrentFilter({
      ...currentFilter,
      allowed_categories: [],
      blocked_categories: [],
    });
  };

  const applyFocusPreset = (preset: "all" | "politics_business" | "sports_world") => {
    if (preset === "all") {
      resetAllBeats();
    } else if (preset === "politics_business") {
      setCurrentFilter({
        ...currentFilter,
        allowed_categories: ["Politics", "Business"],
        blocked_categories: [],
      });
    } else if (preset === "sports_world") {
      setCurrentFilter({
        ...currentFilter,
        allowed_categories: ["Sports", "World Affairs"],
        blocked_categories: [],
      });
    }
  };

  // Keyword management
  const addKeyword = (list: "allowed" | "blocked") => {
    const raw = list === "allowed" ? newKeywordInput.trim() : newBlockedKwInput.trim();
    if (!raw) return;
    const field = list === "allowed" ? "allowed_keywords" : "blocked_keywords";
    const lower = raw.toLowerCase();
    if (!currentFilter[field].some((k) => k.toLowerCase() === lower)) {
      setCurrentFilter({
        ...currentFilter,
        [field]: [...currentFilter[field], raw],
      });
    }
    if (list === "allowed") setNewKeywordInput("");
    else setNewBlockedKwInput("");
  };

  const removeKeyword = (kw: string, list: "allowed" | "blocked") => {
    const field = list === "allowed" ? "allowed_keywords" : "blocked_keywords";
    const lower = kw.toLowerCase();
    setCurrentFilter({
      ...currentFilter,
      [field]: currentFilter[field].filter((k) => k.toLowerCase() !== lower),
    });
  };

  // Unified Save Function
  const saveAllSettings = async () => {
    const total = Number(telegramTotal);
    const et = Number(ethiopiaQuota);
    const intl = Number(internationalQuota);
    const fh = Number(freshnessHours);

    if (![total, et, intl].every(Number.isInteger) || total < 0 || total > 24 || et < 0 || intl < 0 || et + intl !== total) {
      setToastMessage({
        text: "Quotas must be whole numbers (0–24) and Ethiopia + International must equal Total.",
        success: false,
      });
      return;
    }
    if (!Number.isInteger(fh) || fh < 6 || fh > 168) {
      setToastMessage({
        text: "Freshness window must be an integer between 6 and 168 hours.",
        success: false,
      });
      return;
    }

    setIsSaving(true);
    setToastMessage(null);
    try {
      await api.updateTelegramPublishingSettings({
        posts_per_day: total,
        ethiopia_posts_per_day: et,
        international_posts_per_day: intl,
        freshness_hours: fh,
        bypass_freshness_for_breaking: bypassBreaking,
      });

      const updatedFilters = await api.updateContentFilters({
        ethiopia: ethiopiaFilter,
        international: internationalFilter,
      });

      setTelegram(updatedFilters);
      setToastMessage({
        text: `Publishing strategy saved! ${et} Ethiopia + ${intl} International daily posts configured.`,
        success: true,
      });
    } catch (e) {
      setToastMessage({
        text: e instanceof Error ? e.message : "Failed to save settings.",
        success: false,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <PageShell title="Publishing Command Center">
      {/* ─── Hero Header & Channel Identity Strip ─── */}
      <div className="mb-6 rounded-card border border-white/[0.08] bg-ink-900/90 p-5 backdrop-blur-md shadow-card">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="h-3 w-3 rounded-full bg-accent-green animate-pulse" />
              <h2 className="text-xl font-bold text-paper-100 flex items-center gap-2">
                Telegram Channel Dispatch
                <span className="font-mono text-xs font-normal text-paper-400 bg-ink-800 px-2.5 py-0.5 rounded-full border border-white/[0.06]">
                  {telegram?.channel_username || "@Ethiopantimes"}
                </span>
              </h2>
            </div>
            <p className="text-xs text-paper-400 max-w-2xl">
              Autonomous editorial publisher. Curates, translates into Amharic &amp; English, designs visual cards, and broadcasts high-impact news directly to your Telegram subscribers.
            </p>
          </div>

          {/* Channel Badges & Actions */}
          <div className="flex flex-wrap items-center gap-2.5">
            <Badge variant={telegram?.enabled ? "green" : "muted"} className="text-xs py-1 px-3">
              {telegram?.enabled ? "● Automation Active" : "⏸ Paused"}
            </Badge>

            <Badge variant={telegram?.dry_run ? "gold" : "green"} className="text-xs py-1 px-3">
              {telegram?.dry_run ? "🧪 Dry-run (Simulation)" : "🚀 Live Broadcasting"}
            </Badge>

            <Button
              size="sm"
              variant={telegram?.enabled ? "outline" : "default"}
              onClick={async () => {
                try {
                  const v = await api.updateTelegramPublishingSettings({ enabled: !telegram?.enabled });
                  setTelegram(v);
                  setToastMessage({
                    text: v.enabled ? "Automation resumed." : "Automation paused.",
                    success: true,
                  });
                } catch (e) {
                  setToastMessage({ text: e instanceof Error ? e.message : "Error toggling automation", success: false });
                }
              }}
            >
              {telegram?.enabled ? "Pause" : "Enable"}
            </Button>

            <Button
              size="sm"
              variant="outline"
              onClick={async () => {
                try {
                  const nextDryRun = !telegram?.dry_run;
                  const v = await api.updateTelegramPublishingSettings({ dry_run: nextDryRun });
                  setTelegram(v);
                  setToastMessage({
                    text: v.dry_run ? "Switched to Dry-run simulation." : "Switched to Live publishing.",
                    success: true,
                  });
                } catch (e) {
                  setToastMessage({ text: e instanceof Error ? e.message : "Error toggling mode", success: false });
                }
              }}
            >
              {telegram?.dry_run ? "Go Live" : "Simulate"}
            </Button>

            <Button
              size="sm"
              variant="subtle"
              disabled={testingBroadcast}
              onClick={async () => {
                setTestingBroadcast(true);
                setTestResult(null);
                try {
                  const res = await api.testTelegramPost();
                  setTestResult(res);
                  setToastMessage({
                    text: res.message || "Test dispatch broadcast successfully.",
                    success: res.success,
                  });
                } catch (e) {
                  setToastMessage({
                    text: e instanceof Error ? e.message : "Test broadcast failed.",
                    success: false,
                  });
                } finally {
                  setTestingBroadcast(false);
                }
              }}
            >
              {testingBroadcast ? (
                <span className="flex items-center gap-1.5">
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Broadcasting…
                </span>
              ) : (
                <span className="flex items-center gap-1.5">
                  <Send className="h-3.5 w-3.5 text-sky-400" /> Test Dispatch
                </span>
              )}
            </Button>
          </div>
        </div>

        {testResult && (
          <div className="mt-4 rounded-card border border-sky-500/30 bg-sky-950/20 p-3 text-xs text-paper-200">
            <div className="font-semibold text-sky-300 flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4" /> {testResult.message}
            </div>
            {testResult.headline && (
              <div className="mt-1 text-paper-300 font-serif">Headline: &ldquo;{testResult.headline}&rdquo;</div>
            )}
            {testResult.telegram_message_id && (
              <div className="mt-0.5 text-[11px] text-paper-400 font-mono">Telegram Message ID: {testResult.telegram_message_id}</div>
            )}
          </div>
        )}
      </div>

      {/* ─── Navigation Tabs ─── */}
      <div className="flex items-center gap-1 border-b border-white/[0.08] mb-6 pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("mix")}
          className={`flex items-center gap-2 px-4 py-2 rounded-card text-xs font-semibold transition-all ${
            activeTab === "mix"
              ? "bg-accent-green text-ink-950 shadow-sm"
              : "text-paper-400 hover:text-paper-100 hover:bg-white/[0.04]"
          }`}
        >
          <Sliders className="h-3.5 w-3.5" />
          1. Content Mix &amp; Quotas
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("beats")}
          className={`flex items-center gap-2 px-4 py-2 rounded-card text-xs font-semibold transition-all ${
            activeTab === "beats"
              ? "bg-accent-green text-ink-950 shadow-sm"
              : "text-paper-400 hover:text-paper-100 hover:bg-white/[0.04]"
          }`}
        >
          <Layers className="h-3.5 w-3.5" />
          2. News Beats &amp; Classifications
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("shield")}
          className={`flex items-center gap-2 px-4 py-2 rounded-card text-xs font-semibold transition-all ${
            activeTab === "shield"
              ? "bg-accent-green text-ink-950 shadow-sm"
              : "text-paper-400 hover:text-paper-100 hover:bg-white/[0.04]"
          }`}
        >
          <ShieldCheck className="h-3.5 w-3.5" />
          3. Ad Shield &amp; Keywords
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("system")}
          className={`flex items-center gap-2 px-4 py-2 rounded-card text-xs font-semibold transition-all ${
            activeTab === "system"
              ? "bg-accent-green text-ink-950 shadow-sm"
              : "text-paper-400 hover:text-paper-100 hover:bg-white/[0.04]"
          }`}
        >
          <SettingsIcon className="h-3.5 w-3.5" />
          4. Infrastructure &amp; Secrets
        </button>
      </div>

      {/* ─── TAB 1: Content Mix & Quotas ─── */}
      {activeTab === "mix" && (
        <div className="space-y-6">
          <Card className="border-accent-green/30">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Daily Editorial Balance</span>
                <span className="text-xs font-normal font-mono text-paper-400">
                  Target: {totalNum} posts / 24 hrs
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <p className="text-sm text-paper-300">
                Determine the proportion of domestic Ethiopian news (published in Amharic) versus global international news (published in English).
              </p>

              {/* Visual Split Bar */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-mono font-medium">
                  <span className="text-accent-green flex items-center gap-1.5">
                    🇪🇹 Ethiopia &amp; Diaspora ({etNum} posts • {etPct}%)
                  </span>
                  <span className="text-sky-400 flex items-center gap-1.5">
                    🌍 International &amp; Sports ({intlNum} posts • {intlPct}%)
                  </span>
                </div>

                <div className="h-3.5 w-full overflow-hidden rounded-full bg-ink-800 flex border border-white/[0.08]">
                  <div
                    style={{ width: `${Math.max(5, Math.min(95, etPct))}%` }}
                    className="h-full bg-gradient-to-r from-emerald-500 to-accent-green transition-all duration-300"
                  />
                  <div
                    style={{ width: `${Math.max(5, Math.min(95, intlPct))}%` }}
                    className="h-full bg-gradient-to-r from-sky-500 to-blue-600 transition-all duration-300"
                  />
                </div>
              </div>

              {/* Ratio Presets */}
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <span className="text-xs text-paper-500 mr-1">Quick Presets:</span>
                <button
                  type="button"
                  onClick={() => applyPreset(0.6)}
                  className={`px-2.5 py-1 rounded-full text-xs font-mono border transition-all ${
                    etPct === 60
                      ? "border-accent-green bg-accent-green/20 text-accent-green font-bold"
                      : "border-white/[0.08] text-paper-400 hover:text-paper-100 hover:border-white/[0.2]"
                  }`}
                >
                  Balanced (60% ET / 40% Intl)
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset(0.8)}
                  className={`px-2.5 py-1 rounded-full text-xs font-mono border transition-all ${
                    etPct === 80
                      ? "border-accent-green bg-accent-green/20 text-accent-green font-bold"
                      : "border-white/[0.08] text-paper-400 hover:text-paper-100 hover:border-white/[0.2]"
                  }`}
                >
                  Ethiopia First (80% ET / 20% Intl)
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset(0.5)}
                  className={`px-2.5 py-1 rounded-full text-xs font-mono border transition-all ${
                    etPct === 50
                      ? "border-accent-green bg-accent-green/20 text-accent-green font-bold"
                      : "border-white/[0.08] text-paper-400 hover:text-paper-100 hover:border-white/[0.2]"
                  }`}
                >
                  Equal Split (50% ET / 50% Intl)
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset(0.4)}
                  className={`px-2.5 py-1 rounded-full text-xs font-mono border transition-all ${
                    etPct === 40
                      ? "border-accent-green bg-accent-green/20 text-accent-green font-bold"
                      : "border-white/[0.08] text-paper-400 hover:text-paper-100 hover:border-white/[0.2]"
                  }`}
                >
                  International Heavy (40% ET / 60% Intl)
                </button>
              </div>

              {/* Exact Integer Quota Inputs */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
                <div className="rounded-lg border border-white/[0.08] bg-ink-950/60 p-3 space-y-1.5">
                  <label className="text-xs uppercase font-mono tracking-label text-paper-400 block">
                    Total Daily Posts
                  </label>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleTotalChange(String(Math.max(1, totalNum - 1)))}
                      className="h-8 w-8 rounded border border-white/[0.1] bg-ink-900 text-paper-300 hover:bg-white/[0.06] text-center font-bold"
                    >
                      -
                    </button>
                    <Input
                      type="number"
                      min="0"
                      max="24"
                      value={telegramTotal}
                      onChange={(e) => handleTotalChange(e.target.value)}
                      className="text-center font-mono font-bold"
                    />
                    <button
                      type="button"
                      onClick={() => handleTotalChange(String(Math.min(24, totalNum + 1)))}
                      className="h-8 w-8 rounded border border-white/[0.1] bg-ink-900 text-paper-300 hover:bg-white/[0.06] text-center font-bold"
                    >
                      +
                    </button>
                  </div>
                  <span className="text-[11px] text-paper-500 block">Total items planned each day</span>
                </div>

                <div className="rounded-lg border border-accent-green/20 bg-accent-green/5 p-3 space-y-1.5">
                  <label className="text-xs uppercase font-mono tracking-label text-accent-green block">
                    🇪🇹 Ethiopia Posts
                  </label>
                  <Input
                    type="number"
                    min="0"
                    max="24"
                    value={ethiopiaQuota}
                    onChange={(e) => handleEthiopiaChange(e.target.value)}
                    className="font-mono font-bold border-accent-green/30"
                  />
                  <span className="text-[11px] text-accent-green/70 block">Dispatched in Amharic</span>
                </div>

                <div className="rounded-lg border border-sky-500/20 bg-sky-950/10 p-3 space-y-1.5">
                  <label className="text-xs uppercase font-mono tracking-label text-sky-400 block">
                    🌍 International Posts
                  </label>
                  <Input
                    type="number"
                    min="0"
                    max="24"
                    value={internationalQuota}
                    onChange={(e) => handleInternationalChange(e.target.value)}
                    className="font-mono font-bold border-sky-500/30"
                  />
                  <span className="text-[11px] text-sky-400/70 block">Dispatched in English</span>
                </div>
              </div>

              {/* Timing & Freshness Controls */}
              <div className="rounded-card border border-white/[0.08] bg-ink-950/40 p-4 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h4 className="text-xs font-semibold text-paper-200 flex items-center gap-1.5">
                      <Clock className="h-3.5 w-3.5 text-amber-400" />
                      Story Freshness Window
                    </h4>
                    <p className="text-[11px] text-paper-400">
                      Only stories occurring within this timeframe are eligible to be planned for publishing.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      type="number"
                      min="6"
                      max="168"
                      value={freshnessHours}
                      onChange={(e) => setFreshnessHours(e.target.value)}
                      className="w-20 font-mono text-center h-8 text-xs font-bold"
                    />
                    <span className="text-xs text-paper-400 font-mono">hours</span>
                  </div>
                </div>

                <label className="flex items-center gap-2 cursor-pointer pt-2 border-t border-white/[0.06]">
                  <input
                    type="checkbox"
                    checked={bypassBreaking}
                    onChange={(e) => setBypassBreaking(e.target.checked)}
                    className="h-4 w-4 rounded border-ink-600 bg-ink-800 text-accent-green focus:ring-accent-green/20"
                  />
                  <span className="text-xs text-paper-300">
                    <strong className="text-paper-100">Bypass freshness for breaking news</strong> — Always publish high-impact developing alerts regardless of event age.
                  </span>
                </label>
              </div>

              {/* Scheduled Hours Reference */}
              <div className="rounded-card border border-white/[0.06] bg-ink-950/20 p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                <span className="text-paper-400 flex items-center gap-1.5">
                  <Radio className="h-3.5 w-3.5 text-accent-green" />
                  Scheduled Slot Hours (Addis Ababa EAT):
                </span>
                <div className="flex flex-wrap gap-1.5 font-mono">
                  {(telegram?.posting_hours || [8, 11, 14, 17, 20]).map((h) => (
                    <span key={h} className="bg-ink-800 px-2 py-0.5 rounded text-paper-300 border border-white/[0.06]">
                      {h}:00 EAT
                    </span>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ─── TAB 2: News Beats & Classifications ─── */}
      {activeTab === "beats" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-card border border-white/[0.08] bg-ink-900/60">
            <div>
              <h3 className="text-sm font-bold text-paper-100">Select Stream to Configure</h3>
              <p className="text-xs text-paper-400">
                Control which news beats are allowed or blocked for each target audience.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setActiveStream("ethiopia")}
                className={`px-4 py-2 rounded-card text-xs font-semibold flex items-center gap-2 border transition-all ${
                  activeStream === "ethiopia"
                    ? "border-accent-green bg-accent-green/20 text-accent-green font-bold shadow-xs"
                    : "border-white/[0.08] text-paper-400 hover:bg-white/[0.04]"
                }`}
              >
                🇪🇹 Ethiopia Stream (Amharic)
                {ethiopiaFilter.allowed_categories.length > 0 && (
                  <Badge variant="green" className="text-[10px] px-1.5 py-0">
                    {ethiopiaFilter.allowed_categories.length} filtered
                  </Badge>
                )}
              </button>

              <button
                type="button"
                onClick={() => setActiveStream("international")}
                className={`px-4 py-2 rounded-card text-xs font-semibold flex items-center gap-2 border transition-all ${
                  activeStream === "international"
                    ? "border-sky-500 bg-sky-500/20 text-sky-400 font-bold shadow-xs"
                    : "border-white/[0.08] text-paper-400 hover:bg-white/[0.04]"
                }`}
              >
                🌍 International Stream (English)
                {internationalFilter.allowed_categories.length > 0 && (
                  <Badge variant="blue" className="text-[10px] px-1.5 py-0">
                    {internationalFilter.allowed_categories.length} filtered
                  </Badge>
                )}
              </button>
            </div>
          </div>

          <Card className="border-white/[0.08]">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  {activeStream === "ethiopia" ? "🇪🇹 Ethiopian News Beats" : "🌍 International News Beats"}
                  <span className="text-xs font-normal text-paper-400 font-sans">
                    — Click cards to include or exclude specific topics
                  </span>
                </CardTitle>
              </div>

              <div className="flex items-center gap-1.5">
                <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => applyFocusPreset("all")}>
                  Allow All Beats
                </Button>
                <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => applyFocusPreset("politics_business")}>
                  Politics + Business Focus
                </Button>
                <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => applyFocusPreset("sports_world")}>
                  Sports + World Focus
                </Button>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="text-xs text-paper-400 bg-ink-950/40 p-3 rounded-card border border-white/[0.06] flex items-center justify-between">
                <span>
                  <strong>Tip:</strong> Leaving all beats unselected allows all legitimate news categories. If you select one or more beats, ETHIO-TIMES will publish <strong>only</strong> those whitelisted topics to this stream.
                </span>
                <span className="font-mono text-paper-300 ml-2">
                  {currentFilter.allowed_categories.length === 0
                    ? "Mode: All topics permitted"
                    : `Mode: ${currentFilter.allowed_categories.length} topics whitelisted`}
                </span>
              </div>

              {/* Grid of Beat Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {BEAT_DEFINITIONS.map((beat) => {
                  const allowed = isBeatWhitelisted(beat.id);
                  const blocked = isBeatBlocked(beat.id);
                  const isDefaultActive = currentFilter.allowed_categories.length === 0 && !blocked;

                  return (
                    <div
                      key={beat.id}
                      className={`p-4 rounded-card border transition-all duration-200 flex flex-col justify-between gap-3 ${
                        allowed
                          ? "border-accent-green/60 bg-accent-green/10 shadow-xs"
                          : blocked
                          ? "border-red-500/40 bg-red-950/20 opacity-70"
                          : "border-white/[0.08] bg-ink-900/70 hover:border-white/[0.18]"
                      }`}
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="p-1.5 rounded-card bg-ink-800 border border-white/[0.06]">
                              {beat.icon}
                            </span>
                            <span className="font-semibold text-sm text-paper-100">{beat.name}</span>
                          </div>

                          <div>
                            {allowed ? (
                              <Badge variant="green" className="text-[10px] py-0.5">
                                <Check className="h-3 w-3 mr-1" /> Whitelisted
                              </Badge>
                            ) : blocked ? (
                              <Badge variant="red" className="text-[10px] py-0.5">
                                <X className="h-3 w-3 mr-1" /> Excluded
                              </Badge>
                            ) : isDefaultActive ? (
                              <Badge variant="muted" className="text-[10px] py-0.5">
                                Eligible (All)
                              </Badge>
                            ) : (
                              <Badge variant="muted" className="text-[10px] py-0.5 opacity-60">
                                Inactive
                              </Badge>
                            )}
                          </div>
                        </div>

                        <p className="text-xs text-paper-400 leading-relaxed">
                          {beat.description}
                        </p>
                      </div>

                      {/* Action buttons on card */}
                      <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/[0.04]">
                        <Button
                          size="sm"
                          variant={allowed ? "default" : "outline"}
                          onClick={() => toggleBeatAllow(beat.id)}
                          className={`text-xs h-7 px-2.5 ${allowed ? "bg-accent-green text-ink-950 font-bold" : ""}`}
                        >
                          {allowed ? "✓ Whitelisted" : "Whitelist Beat"}
                        </Button>
                        <Button
                          size="sm"
                          variant={blocked ? "destructive" : "subtle"}
                          onClick={() => toggleBeatBlock(beat.id)}
                          className={`text-xs h-7 px-2.5 ${blocked ? "border-red-500 bg-red-900/40 text-red-300" : "text-paper-500 hover:text-red-400"}`}
                        >
                          {blocked ? "✕ Blocked" : "Block"}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Status summary of current filter */}
              <div className="flex items-center justify-between text-xs text-paper-400 pt-2 border-t border-white/[0.06]">
                <div>
                  <strong>Active Filter:</strong>{" "}
                  {currentFilter.allowed_categories.length > 0
                    ? `Only: ${currentFilter.allowed_categories.join(", ")}`
                    : "All legitimate news topics included"}
                  {currentFilter.blocked_categories.length > 0 && (
                    <span className="text-red-400 ml-2">
                      (Blocked: {currentFilter.blocked_categories.join(", ")})
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={resetAllBeats}
                  className="text-xs text-paper-500 hover:text-paper-200 underline"
                >
                  Reset beats to default
                </button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ─── TAB 3: Ad Shield & Custom Keywords ─── */}
      {activeTab === "shield" && (
        <div className="space-y-6">
          <Card className="border-red-500/30 bg-ink-900/80">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base text-paper-100">
                <ShieldCheck className="h-5 w-5 text-accent-green" />
                Autonomous Ad &amp; Sponsored Content Shield
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-paper-300">
                To preserve high editorial credibility on your Telegram channel, ETHIO-TIMES automatically intercepts and rejects commercial promotions, brand advertisements, and PR announcements before they are considered for dispatch.
              </p>

              <div className="rounded-card border border-accent-green/30 bg-accent-green/5 p-3.5 flex items-start gap-3 text-xs text-accent-green">
                <CheckCircle2 className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                  <strong className="block text-paper-100 font-semibold mb-0.5">
                    Permanent Bilingual Protection Enabled
                  </strong>
                  Content matching promotional markers in Amharic (Fidel) or English is automatically discarded from Telegram queue planning.
                </div>
              </div>

              {/* Pre-configured shielded terms */}
              <div>
                <span className="text-xs font-mono uppercase tracking-label text-paper-400 block mb-2">
                  Built-in Protected Signals (Always Screened)
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {DEFAULT_BLOCKED_TERMS.map((term) => (
                    <span
                      key={term}
                      className="px-2.5 py-1 rounded-full text-xs font-mono bg-ink-950 border border-white/[0.08] text-red-300"
                    >
                      ✕ {term}
                    </span>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Custom Keywords Configuration */}
          <Card className="border-white/[0.08]">
            <CardHeader>
              <CardTitle className="text-base">Custom Editorial Keyword Filters</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Blocked Custom Keywords */}
              <div className="space-y-3">
                <div>
                  <h4 className="text-xs font-semibold text-paper-200">
                    Additional Blocked Keywords ({activeStream === "ethiopia" ? "🇪🇹 Ethiopia Feed" : "🌍 International Feed"})
                  </h4>
                  <p className="text-[11px] text-paper-400">
                    Any news event containing these words in its headline or summary will be skipped for this channel.
                  </p>
                </div>

                <div className="flex gap-2 max-w-md">
                  <Input
                    placeholder="e.g. lottery, coupon, discount..."
                    value={newBlockedKwInput}
                    onChange={(e) => setNewBlockedKwInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addKeyword("blocked");
                      }
                    }}
                    className="h-8 text-xs font-mono"
                  />
                  <Button size="sm" className="h-8 text-xs" onClick={() => addKeyword("blocked")}>
                    Add Word
                  </Button>
                </div>

                <div className="flex flex-wrap gap-1.5 pt-1">
                  {currentFilter.blocked_keywords
                    .filter((k) => !DEFAULT_BLOCKED_TERMS.includes(k))
                    .map((kw) => (
                      <span
                        key={kw}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-red-950/40 border border-red-800/60 text-red-300"
                      >
                        {kw}
                        <button
                          type="button"
                          onClick={() => removeKeyword(kw, "blocked")}
                          className="hover:text-white"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  {currentFilter.blocked_keywords.filter((k) => !DEFAULT_BLOCKED_TERMS.includes(k)).length === 0 && (
                    <span className="text-xs text-paper-500 italic">No custom blocked keywords added yet.</span>
                  )}
                </div>
              </div>

              <div className="border-t border-white/[0.06] pt-4 space-y-3">
                <div>
                  <h4 className="text-xs font-semibold text-paper-200">
                    Required Whitelist Keywords (Optional)
                  </h4>
                  <p className="text-[11px] text-paper-400">
                    If configured, stories MUST contain at least one of these words to be planned. Leave empty for standard topic matching.
                  </p>
                </div>

                <div className="flex gap-2 max-w-md">
                  <Input
                    placeholder="e.g. diplomacy, horn of africa..."
                    value={newKeywordInput}
                    onChange={(e) => setNewKeywordInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addKeyword("allowed");
                      }
                    }}
                    className="h-8 text-xs font-mono"
                  />
                  <Button size="sm" className="h-8 text-xs" onClick={() => addKeyword("allowed")}>
                    Add Word
                  </Button>
                </div>

                <div className="flex flex-wrap gap-1.5 pt-1">
                  {currentFilter.allowed_keywords.map((kw) => (
                    <span
                      key={kw}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-accent-green/20 border border-accent-green/50 text-accent-green"
                    >
                      {kw}
                      <button
                        type="button"
                        onClick={() => removeKeyword(kw, "allowed")}
                        className="hover:text-white"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  {currentFilter.allowed_keywords.length === 0 && (
                    <span className="text-xs text-paper-500 italic">Empty (allow all matching beat stories without keyword restrictions).</span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ─── TAB 4: Infrastructure & Secrets ─── */}
      {activeTab === "system" && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Publishing Environment</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Row
                label="Backend API Endpoint"
                value={process.env.NEXT_PUBLIC_API_BASE_URL || "https://ethiotimes-backend.onrender.com"}
              />
              <Row label="Timezone Reference" value={telegram?.timezone || "Africa/Addis_Ababa"} />
              <Row label="Bot Authentication" value={telegram?.bot_configured ? "Token Active" : "Missing Token"} />
              <Row label="Delivery Method" value="Automated Celery / FastAPI Worker" />
              <Row label="Cycle Interval" value="Every 10 minutes" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Channel Credentials</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-xs text-paper-400">
                Sensitive bot tokens are securely injected via environment variables on the backend and never exposed in the browser.
              </p>
              <Row label="TELEGRAM_BOT_TOKEN" value={<Badge variant={telegram?.bot_configured ? "green" : "red"}>{telegram?.bot_configured ? "Configured" : "Missing"}</Badge>} />
              <Row label="TELEGRAM_CHANNEL_USERNAME" value={<Badge variant="muted">{telegram?.channel_username || "@Ethiopantimes"}</Badge>} />
              <Row label="INSTAGRAM_ACCESS_TOKEN" value={<Badge variant="muted">Configured</Badge>} />
            </CardContent>
          </Card>
        </div>
      )}

      {/* ─── Persistent Bottom Sticky Action Bar ─── */}
      <div className="sticky bottom-4 mt-8 rounded-card border border-white/[0.12] bg-ink-950/95 p-4 backdrop-blur-lg shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-0.5">
          <div className="text-xs font-bold text-paper-100 flex items-center gap-2">
            <span>Publishing Strategy Summary</span>
            <Badge variant="muted" className="font-mono text-[10px]">
              {totalNum} posts/day
            </Badge>
          </div>
          <p className="text-xs text-paper-400">
            🇪🇹 {ethiopiaQuota} Ethiopia ({etPct}%) in Amharic + 🌍 {internationalQuota} International ({intlPct}%) in English • Freshness: {freshnessHours}h • Ad Shield: Active
          </p>
        </div>

        <div className="flex items-center gap-3">
          {toastMessage && (
            <span
              role="status"
              className={`text-xs font-semibold ${toastMessage.success ? "text-accent-green" : "text-red-400"}`}
            >
              {toastMessage.text}
            </span>
          )}

          <Button
            onClick={saveAllSettings}
            disabled={isSaving}
            className="bg-accent-green hover:bg-accent-green/90 text-ink-950 font-bold px-6 shadow-sm"
          >
            {isSaving ? (
              <span className="flex items-center gap-2">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Saving Strategy…
              </span>
            ) : (
              "Save All Settings"
            )}
          </Button>
        </div>
      </div>
    </PageShell>
  );
}
