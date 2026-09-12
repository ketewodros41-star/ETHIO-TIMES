"use client";

import { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_BASE, api } from "@/lib/api";
import type { PublishingSettings, TelegramPublishingSettings } from "@/lib/types";

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
              value="http://127.0.0.1:8000"
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
    </PageShell>
  );
}
