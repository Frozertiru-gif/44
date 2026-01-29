"use client";

import { useEffect, useMemo, useState } from "react";
import { IssueCategory, siteContent } from "@/src/content/site";
import { LeadForm } from "@/src/components/LeadForm";
import { Modal } from "@/src/components/Modal";
import { CategoryGrid } from "@/src/components/CategoryGrid";
import { IssuesSection } from "@/src/components/IssuesSection";
import { track } from "@/src/lib/track";

type LeadContext = {
  categoryId?: IssueCategory["id"];
  categoryTitle?: string;
  issueTitle?: string;
  source?: string;
};

export default function Home() {
  const [isFormOpen, setFormOpen] = useState(false);
  const [isMessengerOpen, setMessengerOpen] = useState(false);
  const [activeCategoryId, setActiveCategoryId] = useState<IssueCategory["id"] | null>(null);
  const [leadContext, setLeadContext] = useState<LeadContext | null>(null);

  useEffect(() => {
    const hash = window.location.hash.replace("#", "");
    if (hash && ["pc", "tv", "printer", "phone"].includes(hash)) {
      setActiveCategoryId(hash as IssueCategory["id"]);
    }
  }, []);

  useEffect(() => {
    if (!activeCategoryId) {
      window.history.replaceState(
        null,
        "",
        `${window.location.pathname}${window.location.search}`
      );
      return;
    }
    window.history.replaceState(null, "", `#${activeCategoryId}`);
    const section = document.getElementById(activeCategoryId);
    if (!section) return;
    window.setTimeout(() => {
      section.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 60);
  }, [activeCategoryId]);

  const activeCategory = useMemo(
    () => siteContent.issues.find((group) => group.id === activeCategoryId) ?? null,
    [activeCategoryId]
  );

  const presetMessage = useMemo(() => {
    if (!leadContext?.issueTitle) return "";
    return leadContext.issueTitle;
  }, [leadContext]);

  const handleToggleCategory = (id: IssueCategory["id"]) => {
    setActiveCategoryId((current) => (current === id ? null : id));
  };

  const handleOpenForm = (context: LeadContext) => {
    setLeadContext(context);
    const section = document.getElementById("contacts");
    if (section) {
      section.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    setFormOpen(true);
  };

  const contactBadges = [siteContent.city, ...siteContent.areas].slice(0, 3);

  return (
    <div>
      <header id="top">
        <div className="container header-inner">
          <div className="brand">
            <strong>{siteContent.brand.name}</strong>
            <span>{siteContent.brand.tag}</span>
          </div>
          <nav className="nav-links">
            <a href="#choose">Что сломалось</a>
            <a href="#whyme">Почему я</a>
            <a href="#reviews">Отзывы</a>
            <a href="#contacts">Контакты</a>
          </nav>
          <div className="cta-row header-cta">
            <a className="button secondary" href={`tel:${siteContent.phone.tel}`}>
              {siteContent.cta.call}
            </a>
            <button
              className="button primary"
              onClick={() => {
                setLeadContext(null);
                setFormOpen(true);
              }}
            >
              {siteContent.cta.request}
            </button>
          </div>
        </div>
      </header>

      <main>
        <section className="section" id="hero">
          <div className="container hero">
            <div>
              <h1>{siteContent.hero.title}</h1>
              <p>{siteContent.hero.subtitle}</p>
              <ul>
                {siteContent.hero.points.map((point) => (
                  <li key={point}>✅ {point}</li>
                ))}
              </ul>
              <div className="cta-row" style={{ marginTop: 20 }}>
                <a
                  className="button primary"
                  href={`tel:${siteContent.phone.tel}`}
                  onClick={() => track({ name: "cta_call", payload: { source: "hero" } })}
                >
                  {siteContent.cta.call}
                </a>
                <button
                  className="button ghost"
                  onClick={() => setMessengerOpen(true)}
                >
                  {siteContent.cta.write}
                </button>
              </div>
            </div>
            <div className="hero-card">
              <div>
                <h3>Работаю по {siteContent.city}</h3>
                <p>{siteContent.serviceArea.title}</p>
                {siteContent.serviceArea.subtitle ? (
                  <p className="issue-meta">{siteContent.serviceArea.subtitle}</p>
                ) : null}
              </div>
              <div className="badge-row">
                {contactBadges.map((badge) => (
                  <span className="badge" key={badge}>
                    {badge}
                  </span>
                ))}
              </div>
              <div>
                <p className="issue-meta">Режим работы</p>
                <strong>{siteContent.workHours}</strong>
              </div>
              <div>
                <p className="issue-meta">Телефон</p>
                <a href={`tel:${siteContent.phone.tel}`}>
                  {siteContent.phone.display}
                </a>
              </div>
            </div>
          </div>
        </section>

        <section className="section" id="choose">
          <div className="container">
            <h2>Выберите, что сломалось</h2>
            <p>Быстро подскажу по проблемам и предложу решение.</p>
            <CategoryGrid
              categories={siteContent.categories}
              activeCategoryId={activeCategoryId}
              onToggle={handleToggleCategory}
            />
          </div>
        </section>

        {activeCategory ? (
          <IssuesSection
            category={activeCategory}
            onRequest={({ category, issue }) => {
              handleOpenForm({
                categoryId: category.id,
                categoryTitle: category.title,
                issueTitle: issue?.title,
                source: issue ? "issue-card" : "issues-section"
              });
            }}
            onMessenger={() => setMessengerOpen(true)}
          />
        ) : null}

        <section className="section" id="whyme">
          <div className="container">
            <h2>Почему стоит вызвать меня</h2>
            <div className="trust-list">
              {siteContent.trust.map((item) => (
                <div className="trust-item" key={item}>
                  ✅ {item}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section" id="about">
          <div className="container about">
            <div>
              <h2>{siteContent.about.title}</h2>
              <p>{siteContent.about.text}</p>
              <div className="cta-row">
                <a className="button primary" href={`tel:${siteContent.phone.tel}`}>
                  {siteContent.cta.call}
                </a>
                <button
                  className="button ghost"
                  onClick={() => setMessengerOpen(true)}
                >
                  {siteContent.cta.write}
                </button>
              </div>
            </div>
            <div className="photo-placeholder">Фото мастера (позже)</div>
          </div>
        </section>

        <section className="section" id="reviews">
          <div className="container">
            <h2>Отзывы</h2>
            <div className="grid grid-3">
              {siteContent.reviews.map((review) => (
                <div className="card" key={review.name}>
                  <h3>{review.name}</h3>
                  <p className="review">“{review.text}”</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section" id="contacts">
          <div className="container contacts-container">
            <h2>Контакты и заявка</h2>
            <p>
              {siteContent.city}. Звоните или оставляйте заявку — перезвоню и
              уточню детали.
            </p>
            <div className="contacts-grid">
              <div className="contact-card contact-info">
                <h3>Связаться со мной</h3>
                <p>
                  Телефон: <a href={`tel:${siteContent.phone.tel}`}>
                    {siteContent.phone.display}
                  </a>
                </p>
                <p>Работаю: {siteContent.workHours}</p>
                <div className="cta-row contact-actions">
                  <a className="button primary" href={`tel:${siteContent.phone.tel}`}>
                    {siteContent.cta.call}
                  </a>
                  <a className="button ghost" href={siteContent.messengers.whatsapp}>
                    WhatsApp
                  </a>
                  <a className="button ghost" href={siteContent.messengers.telegram}>
                    Telegram
                  </a>
                </div>
              </div>
              <LeadForm
                source="contacts"
                presetMessage={presetMessage}
                leadContext={{
                  categoryId: leadContext?.categoryId,
                  categoryTitle: leadContext?.categoryTitle,
                  issueTitle: leadContext?.issueTitle
                }}
              />
            </div>
          </div>
        </section>
      </main>

      <footer className="container footer">
        <div>© {new Date().getFullYear()} {siteContent.brand.name}</div>
        <div>Частный мастер. Город: {siteContent.city}.</div>
      </footer>

      <div className="bottom-bar">
        <a className="button primary" href={`tel:${siteContent.phone.tel}`}>
          {siteContent.cta.call}
        </a>
        <button className="button secondary" onClick={() => setMessengerOpen(true)}>
          {siteContent.cta.write}
        </button>
        <button
          className="button primary"
          onClick={() => {
            setLeadContext(null);
            setFormOpen(true);
          }}
        >
          {siteContent.cta.request}
        </button>
      </div>

      <Modal open={isMessengerOpen} onClose={() => setMessengerOpen(false)}>
        <div>
          <p>Напишите в удобный мессенджер:</p>
          <div className="cta-row">
            <a className="button primary" href={siteContent.messengers.whatsapp}>
              WhatsApp
            </a>
            <a className="button ghost" href={siteContent.messengers.telegram}>
              Telegram
            </a>
          </div>
        </div>
      </Modal>

      <Modal
        open={isFormOpen}
        onClose={() => {
          setFormOpen(false);
          setLeadContext(null);
        }}
      >
        <LeadForm
          source={leadContext?.source ?? "modal"}
          compact
          presetMessage={presetMessage}
          leadContext={{
            categoryId: leadContext?.categoryId,
            categoryTitle: leadContext?.categoryTitle,
            issueTitle: leadContext?.issueTitle
          }}
          onSuccess={() => setFormOpen(false)}
        />
      </Modal>
    </div>
  );
}
