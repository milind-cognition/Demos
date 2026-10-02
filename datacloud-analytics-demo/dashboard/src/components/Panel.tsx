import type { ReactNode } from "react";

export function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="panel">
      <header className="panel__header">
        <h2 className="panel__title">{title}</h2>
        {subtitle && <p className="panel__subtitle">{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}

export function PageHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <header className="page-header">
      <span className="page-header__eyebrow">{eyebrow}</span>
      <h1 className="page-header__title">{title}</h1>
      <p className="page-header__description">{description}</p>
    </header>
  );
}

export function Notice({ tone = "warning", children }: { tone?: "warning" | "error"; children: ReactNode }) {
  return (
    <div className={`notice notice--${tone}`} role="alert">
      {children}
    </div>
  );
}
