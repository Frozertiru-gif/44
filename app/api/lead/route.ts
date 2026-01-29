import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

const WINDOW_MS = 10 * 60 * 1000;
const MAX_REQUESTS = 5;

type LeadPayload = {
  name?: string;
  phone?: string;
  message?: string;
  hp?: string;
  source?: string;
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

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    const ip = getIp(req);
    if (isRateLimited(ip)) {
      return NextResponse.json({ ok: false, code: "rate_limited" }, { status: 429 });
    }

    const payload = (await req.json()) as LeadPayload;
    if (payload.hp) {
      return NextResponse.json({ ok: false, code: "honeypot" }, { status: 400 });
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
      source: payload.source?.trim() || "unknown"
    };

    await appendLead(lead);
    console.info("[lead]", lead);

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("[lead:error]", error);
    return NextResponse.json({ ok: false, code: "server_error" }, { status: 400 });
  }
}
