export const PHONE_REGEX = /^\+79\d{9}$/;

const stripToDigits = (value: string) => value.replace(/\D/g, "");

type NormalizeOptions = {
  keepPrefixOnEmpty?: boolean;
};

export const normalizePhone = (value: string, options: NormalizeOptions = {}) => {
  const raw = value.trim();
  if (!raw) {
    return "";
  }

  const digits = stripToDigits(raw);
  if (!digits) {
    return options.keepPrefixOnEmpty ? "+7" : "";
  }

  let normalizedDigits = digits;
  if ((normalizedDigits.startsWith("8") || normalizedDigits.startsWith("7")) && normalizedDigits.length === 11) {
    normalizedDigits = `7${normalizedDigits.slice(1)}`;
  }

  if (normalizedDigits.startsWith("7")) {
    normalizedDigits = normalizedDigits.slice(1);
  }

  const rest = normalizedDigits.slice(0, 10);
  return `+7${rest}`;
};

export const isValidPhone = (value: string) => PHONE_REGEX.test(value);
