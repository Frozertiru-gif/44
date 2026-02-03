import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { randomUUID } from "crypto";
import { isValidPhone, normalizePhone } from "@/src/lib/phone";

const WINDOW_MS = 10 * 60 * 1000;
const MAX_REQUESTS = 5;
const MESSAGE_LIMIT = 3700;
const TELEGRAM_TIMEOUT_MS = 4000;

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

const escapeTelegram = (value: string, parseMode: string) => {
  if (parseMode === "MarkdownV2") {
    return value.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, "\\$&");
  }

  if (parseMode === "HTML") {
    return value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  return value;
};

const buildTelegramMessage = (
  lead: {
    external_id: string;
    ts: string;
    name: string | null;
    phone: string;
    message: string | null;
    source: string;
    categoryId?: string | null;
    categoryTitle?: string | null;
    issueTitle?: string | null;
  },
  parseMode: string
) => {
  const context = [lead.categoryTitle, lead.issueTitle].filter(Boolean).join(" / ") || null;
  const safe = (value: string) => escapeTelegram(value, parseMode);
  const lines = [
    "📩 Новая заявка с сайта",
    `ID: ${safe(lead.external_id)}`,
    `Имя: ${safe(lead.name ?? "—")}`,
    `Телефон: ${safe(lead.phone)}`,
    `Сообщение: ${safe(lead.message ?? "—")}`,
    `Источник: ${safe(lead.source)}`,
    context ? `Категория/Проблема: ${safe(context)}` : null,
    `Время: ${safe(lead.ts)}`
  ].filter(Boolean);

  return lines.join("\n").slice(0, MESSAGE_LIMIT);
};

const sendToTelegramChat = async (lead: {
  external_id: string;
  ts: string;
  name: string | null;
  phone: string;
  message: string | null;
  source: string;
  categoryTitle?: string | null;
  issueTitle?: string | null;
}) => {
  const token = process.env.LEADS_TG_BOT_TOKEN;
  const chatId = process.env.LEADS_TG_CHAT_ID;
  const parseMode = process.env.LEADS_TG_PARSE_MODE ?? "HTML";

  if (!token || !chatId) {
    console.info("[lead:tg] skipped (env not configured)");
    return;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TELEGRAM_TIMEOUT_MS);
  const message = buildTelegramMessage(lead, parseMode);
  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text: message, parse_mode: parseMode }),
      signal: controller.signal
    });
    const body = await response.text().catch(() => "unknown");
    if (!response.ok) {
      console.error("[lead:tg] failed", { status: response.status, body });
      return;
    }
    let data: any = null;
    if (body) {
      try {
        data = JSON.parse(body);
      } catch {
        data = null;
      }
    }
    console.info("[lead:tg] ok", {
      message_id: data?.result?.message_id ?? "unknown",
      chat_id: data?.result?.chat?.id ?? chatId
    });
  } catch (error) {
    console.error("[lead:tg] failed", error);
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

    await sendToTelegramChat(lead);

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("[lead:error]", error);
    return NextResponse.json({ ok: false, code: "server_error" }, { status: 400 });
  }
}
