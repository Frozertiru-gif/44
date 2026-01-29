"use client";

import { useEffect, useState } from "react";
import { track } from "@/src/lib/track";
import { siteContent } from "@/src/content/site";

const normalizePhone = (value: string) => value.replace(/\s+/g, "");

const isValidPhone = (value: string) => {
  const cleaned = value.replace(/[^+\d]/g, "");
  const digits = cleaned.replace(/\D/g, "");
  return digits.length >= 7 && digits.length <= 15;
};

type LeadFormProps = {
  source: string;
  onSuccess?: () => void;
  compact?: boolean;
  presetMessage?: string;
  leadContext?: {
    categoryId?: string;
    categoryTitle?: string;
    issueTitle?: string;
  };
};

export const LeadForm = ({
  source,
  onSuccess,
  compact,
  presetMessage,
  leadContext
}: LeadFormProps) => {
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">(
    "idle"
  );
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState(presetMessage ?? "");

  useEffect(() => {
    setMessage(presetMessage ?? "");
  }, [presetMessage]);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = {
      name: String(formData.get("name") ?? "").trim(),
      phone: normalizePhone(String(formData.get("phone") ?? "").trim()),
      message: message.trim(),
      hp: String(formData.get("hp") ?? "").trim(),
      source,
      categoryId: leadContext?.categoryId,
      categoryTitle: leadContext?.categoryTitle,
      issueTitle: leadContext?.issueTitle
    };

    if (!payload.phone || !isValidPhone(payload.phone)) {
      setError("Укажите корректный номер телефона.");
      return;
    }

    setStatus("loading");

    try {
      const response = await fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        setStatus("success");
        track({ name: "lead_success", payload: { source } });
        form.reset();
        onSuccess?.();
        return;
      }

      const data = await response.json().catch(() => null);
      const message = data?.code === "rate_limited"
        ? "Слишком часто. Попробуйте чуть позже."
        : "Не получилось отправить. Попробуйте ещё раз.";
      setError(message);
      setStatus("error");
    } catch (err) {
      console.error(err);
      setError("Не получилось отправить. Попробуйте ещё раз.");
      setStatus("error");
    }
  };

  if (status === "success") {
    return (
      <div className="card">
        <h3>{siteContent.cta.successTitle}</h3>
        <p>{siteContent.cta.successText}</p>
        <div className="cta-row">
          <a className="button primary" href={`tel:${siteContent.phone.tel}`}>
            {siteContent.cta.call}
          </a>
          <a className="button ghost" href={siteContent.messengers.whatsapp}>
            WhatsApp
          </a>
          <a className="button ghost" href={siteContent.messengers.telegram}>
            Telegram
          </a>
        </div>
      </div>
    );
  }

  return (
    <form className="contact-card" onSubmit={submit}>
      <div>
        <h3>{siteContent.cta.formTitle}</h3>
        <p>{siteContent.cta.formSubtitle}</p>
      </div>
      <div className="form-row">
        <label className="form-field">
          <span>Имя (необязательно)</span>
          <input name="name" type="text" placeholder="Например, Ольга" />
        </label>
        <label className="form-field">
          <span>Телефон *</span>
          <input
            name="phone"
            type="tel"
            placeholder="+7 900 000-00-00"
            required
          />
        </label>
      </div>
      <label className="form-field">
        <span>Что сломалось (необязательно)</span>
        <textarea
          name="message"
          rows={compact ? 3 : 4}
          placeholder="Например, не включается телевизор"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
      </label>
      <label style={{ display: "none" }}>
        <span>Не заполняйте</span>
        <input name="hp" type="text" autoComplete="off" />
      </label>
      {error ? <p className="form-note">{error}</p> : null}
      <button className="button primary" type="submit" disabled={status === "loading"}>
        {status === "loading" ? "Отправляю..." : siteContent.cta.request}
      </button>
      <p className="form-note">
        Нажимая кнопку, вы соглашаетесь на обработку обращения.
      </p>
    </form>
  );
};
