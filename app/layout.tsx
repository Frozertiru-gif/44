import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ремонт техники на дому — частный мастер",
  description:
    "Ремонт компьютеров, телевизоров, принтеров и телефонов на дому. Быстрый выезд и понятная цена.",
  openGraph: {
    title: "Ремонт техники на дому",
    description:
      "Частный мастер. Диагностика на месте, понятная цена, быстрый выезд.",
    type: "website"
  },
  icons: {
    icon: "/favicon.svg"
  },
  viewport: {
    width: "device-width",
    initialScale: 1
  }
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body>
        {children}
        <div id="modal-root" />
      </body>
    </html>
  );
}
