import type { MetadataRoute } from "next";
import { GEO } from "@/src/content/geo";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://master-nt.space";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  return [
    {
      url: `${siteUrl}/`,
      lastModified,
      priority: 1
    },
    ...GEO.map((geo) => ({
      url: `${siteUrl}/${geo.slug}`,
      lastModified,
      priority: 0.7
    }))
  ];
}
