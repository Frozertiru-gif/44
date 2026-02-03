import type { Metadata } from "next";
import { siteContent, serviceAreaLocalities } from "@/src/content/site";
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
  const localBusinessSchema = {
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    name: `${siteContent.brand.name} — ${siteContent.brand.tag}`,
    telephone: siteContent.phone.tel,
    address: {
      "@type": "PostalAddress",
      addressLocality: siteContent.city,
      addressCountry: "RU"
    },
    areaServed: serviceAreaLocalities
  };

  return (
    <html lang="ru">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(localBusinessSchema) }}
        />
      </head>
      <body>
        {children}
        <div id="modal-root" />
      </body>
    </html>
  );
}
