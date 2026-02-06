type ServicesGridProps = {
  title?: string;
  items: string[];
};

export function ServicesGrid({ title = "Виды техники", items }: ServicesGridProps) {
  if (!items.length) {
    return null;
  }

  return (
    <section className="services-grid" aria-label={title}>
      <h3>{title}</h3>
      <ul>
        {items.map((item) => (
          <li key={item}>
            <span className="services-grid-marker" aria-hidden="true" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
