"use client";

import { siteContent } from "@/src/content/site";

type MessengerButtonsProps = {
  className?: string;
  buttonClassName?: string;
};

const messengerItems = [
  { key: "whatsapp", label: "WhatsApp", url: siteContent.messengers.whatsappUrl },
  { key: "telegram", label: "Telegram", url: siteContent.messengers.telegramUrl },
  { key: "max", label: "MAX", url: siteContent.messengers.maxUrl }
];

export const MessengerButtons = ({
  className,
  buttonClassName = "button ghost"
}: MessengerButtonsProps) => {
  const items = messengerItems.filter((item) => Boolean(item.url));

  return (
    <>
      {items.map((item) => (
        <a
          className={`${buttonClassName}${className ? ` ${className}` : ""}`}
          href={item.url}
          key={item.key}
        >
          {item.label}
        </a>
      ))}
    </>
  );
};
