"use client";

import { SiteContent } from "@/src/content/site";

type CategoryGridProps = {
  categories: SiteContent["categories"];
  activeCategoryId: SiteContent["categories"][number]["id"] | null;
  onToggle: (id: SiteContent["categories"][number]["id"]) => void;
};

export const CategoryGrid = ({
  categories,
  activeCategoryId,
  onToggle
}: CategoryGridProps) => (
  <div className="grid grid-2">
    {categories.map((category) => {
      const isActive = activeCategoryId === category.id;
      return (
        <div className={`card category-card${isActive ? " active" : ""}`} key={category.id}>
          <h3>{category.title}</h3>
          <p>{category.description}</p>
          <button
            className="button ghost"
            onClick={() => onToggle(category.id)}
            aria-expanded={isActive}
            aria-controls={`issues-${category.id}`}
          >
            {isActive ? "Скрыть частые проблемы" : "Посмотреть частые проблемы"}
          </button>
        </div>
      );
    })}
  </div>
);
