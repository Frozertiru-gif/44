import type { Metadata, Viewport } from "next";
import { siteContent } from "@/src/content/site";
import { GEO } from "@/src/content/geo";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://master-nt.space";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
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
  }
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1
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
    areaServed: GEO.map((geo) => ({
      "@type": geo.kind === "city" ? "City" : "Place",
      name: geo.name
    }))
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
