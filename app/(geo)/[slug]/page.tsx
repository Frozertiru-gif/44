import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LandingPage } from "@/src/components/LandingPage";
import { GEO, GEO_BY_SLUG } from "@/src/content/geo";
import { buildGeoCopy, getGeoNameInPrepositional } from "@/src/content/geoCopy";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://master-nt.space";

type GeoPageProps = {
  params: {
    slug: string;
  };
};

export function generateStaticParams() {
  return GEO.map((geo) => ({ slug: geo.slug }));
}

export function generateMetadata({ params }: GeoPageProps): Metadata {
  const geo = GEO_BY_SLUG.get(params.slug);

  if (!geo) {
    return {};
  }

  const copy = buildGeoCopy(geo.name, geo.slug);

  const geoNameInPrepositional = getGeoNameInPrepositional(geo.name, geo.slug);

  return {
    title: `Ремонт техники в ${geoNameInPrepositional} — выезд мастера`,
    description: copy.titleLead,
    alternates: {
      canonical: `${siteUrl}/${geo.slug}`
    }
  };
}

export default function GeoPage({ params }: GeoPageProps) {
  const geo = GEO_BY_SLUG.get(params.slug);

  if (!geo) {
    notFound();
  }

  const copy = buildGeoCopy(geo.name, geo.slug);
  const serviceSchema = {
    "@context": "https://schema.org",
    "@type": "Service",
    serviceType: "Ремонт техники на дому",
    areaServed: {
      "@type": geo.kind === "city" ? "City" : "Place",
      name: geo.name
    },
    provider: {
      "@type": "LocalBusiness",
      name: "Илья — Частный мастер"
    }
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceSchema) }}
      />
      <LandingPage geoName={geo.name} geoSlug={geo.slug} seoCopy={copy} />
    </>
  );
}
