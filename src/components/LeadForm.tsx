"use client";

import { useEffect, useState } from "react";
import { track } from "@/src/lib/track";
import { siteContent } from "@/src/content/site";
import { usePhoneField } from "@/src/components/usePhoneField";
import { MessengerButtons } from "@/src/components/MessengerButtons";

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
  const [formError, setFormError] = useState<string | null>(null);
  const [message, setMessage] = useState(presetMessage ?? "");
  const phoneField = usePhoneField();

  useEffect(() => {
    setMessage(presetMessage ?? "");
  }, [presetMessage]);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    phoneField.markSubmitted();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = {
      name: String(formData.get("name") ?? "").trim(),
      phone: phoneField.value.trim(),
      message: message.trim(),
      hp: String(formData.get("hp") ?? "").trim(),
      source,
      categoryId: leadContext?.categoryId,
      categoryTitle: leadContext?.categoryTitle,
      issueTitle: leadContext?.issueTitle
    };

    if (!phoneField.isValid) {
      phoneField.focus();
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
        phoneField.reset();
        onSuccess?.();
        return;
      }

      const data = await response.json().catch(() => null);
      const message = data?.code === "rate_limited"
        ? "Слишком часто. Попробуйте чуть позже."
        : "Не получилось отправить. Попробуйте ещё раз.";
      setFormError(message);
      setStatus("error");
    } catch (err) {
      console.error(err);
      setFormError("Не получилось отправить. Попробуйте ещё раз.");
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
          <MessengerButtons />
        </div>
      </div>
    );
  }

  const showContextBadge = Boolean(leadContext?.categoryTitle && !leadContext?.issueTitle);

  return (
    <form className={`contact-card${compact ? " compact" : ""}`} onSubmit={submit}>
      <div>
        <h3>{siteContent.cta.formTitle}</h3>
        <p>{siteContent.cta.formSubtitle}</p>
      </div>
      {showContextBadge ? (
        <div className="form-context">
          <span className="badge">{leadContext?.categoryTitle}</span>
        </div>
      ) : null}
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
            placeholder="+79XXXXXXXXX"
            value={phoneField.value}
            onChange={phoneField.handleChange}
            onFocus={phoneField.handleFocus}
            onBlur={phoneField.handleBlur}
            onPaste={phoneField.handlePaste}
            ref={phoneField.inputRef}
            inputMode="tel"
            autoComplete="tel"
            aria-invalid={Boolean(phoneField.error)}
          />
          {phoneField.error ? <span className="form-note">{phoneField.error}</span> : null}
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
      {formError ? <p className="form-note">{formError}</p> : null}
      <div className="form-actions">
        <button
          className="button primary"
          type="submit"
          disabled={status === "loading" || !phoneField.isValid}
        >
          {status === "loading" ? "Отправляю..." : siteContent.cta.request}
        </button>
      </div>
      <p className="form-note">
        Нажимая кнопку, вы соглашаетесь на обработку обращения.
      </p>
    </form>
  );
};
