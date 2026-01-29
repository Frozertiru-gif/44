"use client";

import { useState } from "react";
import { siteContent } from "@/src/content/site";
import { LeadForm } from "@/src/components/LeadForm";
import { Modal } from "@/src/components/Modal";
import { track } from "@/src/lib/track";

const highlightSection = (id: string) => {
  const section = document.getElementById(id);
  if (!section) return;
  section.scrollIntoView({ behavior: "smooth", block: "start" });
  section.classList.add("highlight");
  window.setTimeout(() => section.classList.remove("highlight"), 1200);
};

export default function Home() {
  const [isFormOpen, setFormOpen] = useState(false);
  const [isMessengerOpen, setMessengerOpen] = useState(false);

  const handleTileClick = (id: string) => {
    highlightSection(id);
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
          <div className="cta-row">
            <a className="button secondary" href={`tel:${siteContent.phone.tel}`}>
              {siteContent.cta.call}
            </a>
            <button
              className="button primary"
              onClick={() => setFormOpen(true)}
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
                <p>Выезжаю по районам: {siteContent.areas.join(", ")}</p>
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
            <div className="grid grid-2">
              {siteContent.categories.map((category) => (
                <div className="card" key={category.id}>
                  <h3>{category.title}</h3>
                  <p>{category.description}</p>
                  <button
                    className="button ghost"
                    onClick={() => handleTileClick(category.id)}
                  >
                    Посмотреть частые проблемы
                  </button>
                </div>
              ))}
            </div>
          </div>
        </section>

        {siteContent.issues.map((group) => (
          <section className="section" id={group.id} key={group.id}>
            <div className="container">
              <h2>{group.title}</h2>
              <div className="grid grid-3">
                {group.items.map((item) => (
                  <div className="card issue-card" key={item.title}>
                    <h3>{item.title}</h3>
                    <p className="issue-meta">{item.details}</p>
                    <p className="issue-risk">{item.risk}</p>
                    <p className="issue-meta">{item.action}</p>
                    <div className="cta-row">
                      <a
                        className="button primary"
                        href={`tel:${siteContent.phone.tel}`}
                      >
                        Вызвать мастера
                      </a>
                      <button
                        className="button secondary"
                        onClick={() => setMessengerOpen(true)}
                      >
                        Написать
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        ))}

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
          <div className="container">
            <h2>Контакты и заявка</h2>
            <p>
              {siteContent.city}. Звоните или оставляйте заявку — перезвоню и
              уточню детали.
            </p>
            <div className="grid grid-2">
              <div className="contact-card">
                <h3>Связаться со мной</h3>
                <p>
                  Телефон: <a href={`tel:${siteContent.phone.tel}`}>
                    {siteContent.phone.display}
                  </a>
                </p>
                <p>Работаю: {siteContent.workHours}</p>
                <div className="cta-row">
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
              <LeadForm source="contacts" />
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
        <button className="button primary" onClick={() => setFormOpen(true)}>
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

      <Modal open={isFormOpen} onClose={() => setFormOpen(false)}>
        <LeadForm source="modal" compact onSuccess={() => setFormOpen(false)} />
      </Modal>
    </div>
  );
}
