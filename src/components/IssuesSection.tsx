"use client";

import { useEffect, useRef } from "react";
import { IssueCategory, siteContent } from "@/src/content/site";
import { IssueCard } from "@/src/components/IssueCard";

type IssuesSectionProps = {
  category: IssueCategory;
  onRequest: (context: { category: IssueCategory; issue?: IssueCategory["items"][number] }) => void;
  onMessenger: () => void;
};

export const IssuesSection = ({ category, onRequest, onMessenger }: IssuesSectionProps) => {
  const sectionRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;
    section.classList.add("highlight");
    const timer = window.setTimeout(() => section.classList.remove("highlight"), 1400);
    return () => window.clearTimeout(timer);
  }, [category.id]);

  return (
    <section className="section issues-section" id={category.id} ref={sectionRef}>
      <div className="container">
        <h2>{category.title}</h2>
        <div className="grid grid-3" id={`issues-${category.id}`}>
          {category.items.map((issue) => (
            <IssueCard
              key={issue.title}
              issue={issue}
              category={category}
              onRequest={({ category: selectedCategory, issue: selectedIssue }) =>
                onRequest({ category: selectedCategory, issue: selectedIssue })
              }
              onMessenger={onMessenger}
            />
          ))}
        </div>
        <div className="issues-cta">
          <div>
            <h3>{siteContent.issuesCta.title}</h3>
            <p>{siteContent.issuesCta.subtitle}</p>
          </div>
          <button
            className="button primary"
            type="button"
            onClick={() => onRequest({ category })}
          >
            {siteContent.issuesCta.button}
          </button>
        </div>
      </div>
    </section>
  );
};
