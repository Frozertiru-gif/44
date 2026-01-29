"use client";

import { Issue, IssueCategory } from "@/src/content/site";

type IssueCardProps = {
  issue: Issue;
  category: IssueCategory;
  onRequest: (context: { category: IssueCategory; issue: Issue }) => void;
  onMessenger: () => void;
};

export const IssueCard = ({ issue, category, onRequest, onMessenger }: IssueCardProps) => (
  <div className="card issue-card">
    <h3>{issue.title}</h3>
    <p className="issue-meta">{issue.details}</p>
    <p className="issue-risk">{issue.risk}</p>
    <p className="issue-meta">{issue.action}</p>
    <div className="cta-row">
      <button
        className="button primary"
        type="button"
        onClick={() => onRequest({ category, issue })}
      >
        Вызвать мастера
      </button>
      <button className="button secondary" type="button" onClick={onMessenger}>
        Написать
      </button>
    </div>
  </div>
);
