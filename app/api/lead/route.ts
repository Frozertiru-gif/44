import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { randomUUID } from "crypto";
import { isValidPhone, normalizePhone } from "@/src/lib/phone";

const WINDOW_MS = 10 * 60 * 1000;
const MAX_REQUESTS = 5;
const MESSAGE_LIMIT = 800;

type LeadPayload = {
  name?: string;
  phone?: string;
  message?: string;
  hp?: string;
  source?: string;
  categoryId?: string;
  categoryTitle?: string;
  issueTitle?: string;
};

type RateState = {
  timestamps: number[];
};

const rateMap = new Map<string, RateState>();

const getIp = (req: Request) => {
  const forwarded = req.headers.get("x-forwarded-for");
  if (forwarded) {
    return forwarded.split(",")[0]?.trim();
  }
  return req.headers.get("x-real-ip") ?? "unknown";
};

const isRateLimited = (ip: string) => {
  const now = Date.now();
  const state = rateMap.get(ip) ?? { timestamps: [] };
  state.timestamps = state.timestamps.filter((ts) => now - ts < WINDOW_MS);
  if (state.timestamps.length >= MAX_REQUESTS) {
    rateMap.set(ip, state);
    return true;
  }
  state.timestamps.push(now);
  rateMap.set(ip, state);
  return false;
};

const appendLead = async (lead: Record<string, string | null>) => {
  const dir = path.join(process.cwd(), "data");
  await fs.mkdir(dir, { recursive: true });
  const filePath = path.join(dir, "leads.jsonl");
  await fs.appendFile(filePath, `${JSON.stringify(lead)}\n`, "utf8");
};

const parseAdminIds = (value?: string | null) =>
  (value ?? "")
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((id) => Number.isFinite(id) && id > 0);

const buildTelegramMessage = (lead: {
  ts: string;
  name: string | null;
  phone: string;
  message: string | null;
  source: string;
  categoryId?: string | null;
  categoryTitle?: string | null;
  issueTitle?: string | null;
}) => {
  const context =
    lead.categoryTitle && lead.issueTitle
      ? `${lead.categoryTitle} → ${lead.issueTitle}`
      : lead.categoryTitle
      ? lead.categoryTitle
      : lead.issueTitle
      ? lead.issueTitle
      : null;
  const lines = [
    "<b>Новая заявка</b>",
    `Дата: ${lead.ts}`,
    lead.name ? `Имя: ${lead.name}` : null,
    `Телефон: ${lead.phone}`,
    lead.message ? `Что сломалось: ${lead.message}` : null,
    context ? `Контекст: ${context}` : null,
    `Источник: ${lead.source}`
  ].filter(Boolean);

  return lines.join("\n").slice(0, MESSAGE_LIMIT);
};

const sendTelegramMessage = async (message: string) => {
  const token = process.env.LEADS_TG_BOT_TOKEN;
  const adminIds = parseAdminIds(process.env.LEADS_TG_ADMIN_IDS);
  const parseMode = process.env.LEADS_TG_PARSE_MODE ?? "HTML";

  if (!token || adminIds.length === 0) {
    throw new Error("Telegram env not configured");
  }

  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  await Promise.all(
    adminIds.map(async (chatId) => {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId, text: message, parse_mode: parseMode })
      });
      if (!response.ok) {
        const body = await response.text().catch(() => "unknown");
        throw new Error(`Telegram send failed (${chatId}): ${response.status} ${body}`);
      }
    })
  );
};

const WEBHOOK_TIMEOUT_MS = 4000;

const sendLeadWebhook = async (lead: Record<string, string | null>) => {
  const url = process.env.LEADS_WEBHOOK_URL;
  const secret = process.env.LEADS_WEBHOOK_SECRET;

  if (!url || !secret) {
    throw new Error("Webhook env not configured");
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), WEBHOOK_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Webhook-Secret": secret
      },
      body: JSON.stringify(lead),
      signal: controller.signal
    });

    if (!response.ok) {
      const body = await response.text().catch(() => "unknown");
      throw new Error(`Webhook failed: ${response.status} ${body}`);
    }
  } finally {
    clearTimeout(timer);
  }
};

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    const ip = getIp(req);
    if (isRateLimited(ip)) {
      return NextResponse.json({ ok: false, code: "rate_limited" }, { status: 429 });
    }

    const payload = (await req.json()) as LeadPayload;
    if (payload.hp) {
      return NextResponse.json({ ok: true });
    }

    const phone = normalizePhone(payload.phone ?? "");
    if (!phone || !isValidPhone(phone)) {
      return NextResponse.json({ ok: false, code: "invalid_phone" }, { status: 400 });
    }

    const lead = {
      external_id: randomUUID(),
      ts: new Date().toISOString(),
      ip,
      ua: req.headers.get("user-agent") ?? "unknown",
      name: payload.name?.trim() || null,
      phone,
      message: payload.message?.trim() || null,
      source: payload.source?.trim() || "unknown",
      categoryId: payload.categoryId?.trim() || null,
      categoryTitle: payload.categoryTitle?.trim() || null,
      issueTitle: payload.issueTitle?.trim() || null
    };

    await appendLead(lead);
    console.info("[lead]", lead);

    let delivered = false;
    try {
      await sendLeadWebhook(lead);
      delivered = true;
      console.info("[lead:webhook] delivered", { external_id: lead.external_id });
    } catch (error) {
      console.error("[lead:webhook] failed", error);
    }

    const fallbackEnabled = process.env.LEADS_TG_FALLBACK === "1";
    if (!delivered && fallbackEnabled) {
      try {
        const message = buildTelegramMessage(lead);
        await sendTelegramMessage(message);
        delivered = true;
        console.info("[lead:telegram] delivered", { external_id: lead.external_id });
      } catch (error) {
        console.error("[lead:telegram] failed", error);
      }
    }

    return NextResponse.json({ ok: true, delivered });
  } catch (error) {
    console.error("[lead:error]", error);
    return NextResponse.json({ ok: false, code: "server_error" }, { status: 400 });
  }
}
