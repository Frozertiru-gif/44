const GEO_PREPOSITIONAL_BY_SLUG: Record<string, string> = {
  "nizhniy-tagil": "Нижнем Тагиле",
  "nevjansk": "Невьянске",
  "kirovgrad": "Кировграде",
  "verhnyaya-salda": "Верхней Салде",
  "nizhnyaya-salda": "Нижней Салде",
  "pokrovskoe": "селе Покровском",
  "svobodnyy": "посёлке Свободном",
  "gornouralskiy": "посёлке Горноуральском",
  "nikolo-pavlovskoe": "селе Николо-Павловском",
  "novoasbest": "посёлке Новоасбесте",
  "petrokamenskoe": "селе Петрокаменском",
  "pervomayskiy": "посёлке Первомайском",
  "krasnopolye": "селе Краснополье",
  "chernoistochinsk": "посёлке Черноисточинске",
  "uralets": "посёлке Уральце",
  "visim": "посёлке Висиме"
};

export function getGeoNameInPrepositional(geoName: string, slug: string): string {
  return GEO_PREPOSITIONAL_BY_SLUG[slug] ?? geoName;
}

export function buildGeoCopy(geoName: string, slug: string): {
  titleLead: string;
  bullets: string[];
  body: string[];
  cta: string;
} {
  const geoNameInPrepositional = getGeoNameInPrepositional(geoName, slug);

  return {
    titleLead: `Занимаюсь ремонтом техники в ${geoNameInPrepositional} с выездом на дом. Работаю с компьютерами, ноутбуками, телевизорами, смартфонами и принтерами. Диагностика и стоимость работ согласовываются до начала ремонта.`,
    bullets: [
      "Ремонт и настройка компьютеров и ноутбуков",
      "Ремонт телевизоров и Smart TV",
      "Ремонт смартфонов и планшетов",
      "Ремонт и обслуживание принтеров",
      "Установка и настройка программ"
    ],
    body: [
      `Работаю в ${geoNameInPrepositional} и ближайших районах. В большинстве случаев неисправность удаётся определить и устранить на месте. Если требуется более сложный ремонт, заранее объясняю объём работ и сроки.`,
      "Сколько стоит ремонт техники? Цена зависит от неисправности и модели устройства. Окончательная стоимость называется после диагностики.",
      "Как быстро возможен выезд? Возможен выезд в день обращения, включая вечернее время."
    ],
    cta: "Если техника работает нестабильно — оставьте заявку. Подскажу оптимальный порядок действий уже при первом звонке."
  };
}
