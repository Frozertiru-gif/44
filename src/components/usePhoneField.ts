import type { ChangeEvent, ClipboardEvent } from "react";
import { useCallback, useMemo, useRef, useState } from "react";
import { isValidPhone, normalizePhone } from "@/src/lib/phone";

const focusAtEnd = (input: HTMLInputElement | null) => {
  if (!input) return;
  const length = input.value.length;
  input.setSelectionRange(length, length);
};

export const usePhoneField = () => {
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const isValid = useMemo(() => isValidPhone(value), [value]);
  const shouldShowError = touched || submitAttempted;

  const error = useMemo(() => {
    if (!shouldShowError) return null;
    if (!value) return "Введите номер телефона";
    if (!isValid) return "Номер должен быть в формате +79XXXXXXXXX";
    return null;
  }, [isValid, shouldShowError, value]);

  const handleChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const raw = event.target.value;
    if (!raw) {
      setValue("");
      return;
    }
    setValue(normalizePhone(raw, { keepPrefixOnEmpty: true }));
  }, []);

  const handleFocus = useCallback(() => {
    if (value) return;
    setValue("+7");
    requestAnimationFrame(() => {
      focusAtEnd(inputRef.current);
    });
  }, [value]);

  const handleBlur = useCallback(() => {
    setTouched(true);
  }, []);

  const handlePaste = useCallback((event: ClipboardEvent<HTMLInputElement>) => {
    const text = event.clipboardData.getData("text");
    if (!text) return;
    event.preventDefault();
    setValue(normalizePhone(text, { keepPrefixOnEmpty: true }));
    requestAnimationFrame(() => {
      focusAtEnd(inputRef.current);
    });
  }, []);

  const reset = useCallback(() => {
    setValue("");
    setTouched(false);
    setSubmitAttempted(false);
  }, []);

  const markSubmitted = useCallback(() => {
    setSubmitAttempted(true);
  }, []);

  const focus = useCallback(() => {
    inputRef.current?.focus();
  }, []);

  return {
    value,
    isValid,
    error,
    inputRef,
    handleChange,
    handleFocus,
    handleBlur,
    handlePaste,
    markSubmitted,
    reset,
    focus
  };
};
