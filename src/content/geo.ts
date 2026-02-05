import { readdirSync } from "node:fs";
import { join } from "node:path";

export type GeoItem = {
  slug: string;
  name: string;
  kind?: "city" | "settlement";
};

export const GEO: GeoItem[] = [
  { slug: "nizhniy-tagil", name: "Нижний Тагил", kind: "city" },
  { slug: "nevjansk", name: "Невьянск", kind: "city" },
  { slug: "kirovgrad", name: "Кировград", kind: "city" },
  { slug: "verhnyaya-salda", name: "Верхняя Салда", kind: "city" },
  { slug: "nizhnyaya-salda", name: "Нижняя Салда", kind: "city" },
  { slug: "pokrovskoe", name: "с. Покровское", kind: "settlement" },
  { slug: "svobodnyy", name: "ПГТ Свободный", kind: "settlement" },
  { slug: "gornouralskiy", name: "ПГТ Горноуральский", kind: "settlement" },
  { slug: "nikolo-pavlovskoe", name: "с. Николо-Павловское", kind: "settlement" },
  { slug: "novoasbest", name: "п. Новоасбест", kind: "settlement" },
  { slug: "petrokamenskoe", name: "с. Петрокаменское", kind: "settlement" },
  { slug: "pervomayskiy", name: "п. Первомайский", kind: "settlement" },
  { slug: "krasnopolye", name: "с. Краснополье", kind: "settlement" },
  { slug: "chernoistochinsk", name: "п. Черноисточинск", kind: "settlement" },
  { slug: "uralets", name: "п. Уралец", kind: "settlement" },
  { slug: "visim", name: "п. Висим", kind: "settlement" }
];

export const GEO_BY_SLUG = new Map(GEO.map((g) => [g.slug, g] as const));

function collectReservedRootSlugs() {
  const appDir = join(process.cwd(), "app");
  const entries = readdirSync(appDir, { withFileTypes: true });

  return new Set(
    entries
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .filter((name) => !name.startsWith("(") && !name.startsWith("[") && !name.startsWith("@"))
  );
}

function validateGeoSlugsNoConflicts() {
  const reservedRootSlugs = collectReservedRootSlugs();
  const conflicts = GEO.filter((geo) => reservedRootSlugs.has(geo.slug)).map((geo) => geo.slug);

  if (conflicts.length > 0) {
    throw new Error(
      `[geo] Конфликт slug с существующими root-роутами в app/: ${conflicts.join(", ")}. ` +
      "Измените GEO slug или переименуйте конфликтующий route segment."
    );
  }
}

validateGeoSlugsNoConflicts();
