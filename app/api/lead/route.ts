import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

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

const normalizePhone = (value: string) => value.replace(/[^+\d]/g, "");

const isValidPhone = (value: string) => {
  const digits = value.replace(/\D/g, "");
  return digits.length >= 7 && digits.length <= 15;
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

    try {
      const message = buildTelegramMessage(lead);
      await sendTelegramMessage(message);
    } catch (error) {
      console.error("[lead:telegram]", error);
      return NextResponse.json(
        { ok: false, code: "telegram_failed" },
        { status: 500 }
      );
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("[lead:error]", error);
    return NextResponse.json({ ok: false, code: "server_error" }, { status: 400 });
  }
}
