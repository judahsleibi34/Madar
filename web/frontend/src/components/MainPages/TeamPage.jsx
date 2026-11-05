import FadeIn from "../Animations/FadeIn";
import { getTeamContent } from "../../content";

const icons = {
  linkedin: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4.98 3.5C4.98 4.88 3.86 6 2.5 6S0 4.88 0 3.5 1.12 1 2.5 1s2.48 1.12 2.48 2.5ZM.4 8h4.2v15H.4V8Zm7.1 0h4v2.05h.06c.56-1.06 1.94-2.18 3.99-2.18 4.27 0 5.05 2.81 5.05 6.46V23h-4.2v-7.67c0-1.83-.03-4.18-2.55-4.18-2.55 0-2.94 1.99-2.94 4.05V23H7.5V8Z" />
    </svg>
  ),
  cv: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 2h8l5 5v15H6V2Zm7 1.5V8h4.5L13 3.5ZM8 12h8v2H8v-2Zm0 4h8v2H8v-2Zm0-8h3v2H8V8Z" />
    </svg>
  ),
  email: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 5h18v14H3V5Zm9 8.2L5.4 7H18.6L12 13.2ZM10.8 15 5 9.55V17h14V9.55L13.2 15a1.75 1.75 0 0 1-2.4 0Z" />
    </svg>
  ),
};

export default function TeamPage({ lang = "en" }) {
  const t = getTeamContent(lang);

  return (
    <section id="team" className="team-page" dir={lang === "ar" ? "rtl" : "ltr"}>
      <FadeIn>
        <header className="team-hero app-page-section-heading app-major-section">
          <h2>{t.title}</h2>
          <p>{t.subtitle}</p>
        </header>
      </FadeIn>

      <section className="team-grid" aria-label={t.title}>
        {t.members.map((member, index) => (
          <FadeIn key={member.name} delay={0.15 + index * 0.15}>
            <article className="team-profile-card">
              <div className="profile-glow" />

              <div className="profile-avatar">
                {member.image ? (
                  <img
                    src={member.image}
                    alt={member.name}
                    width={member.imageWidth}
                    height={member.imageHeight}
                    loading="lazy"
                    decoding="async"
                  />
                ) : (
                  <span>{member.initials}</span>
                )}
              </div>

              <div className="profile-content">
                <h3>{member.name}</h3>
                <p className="profile-role">{member.role}</p>
                <p className="profile-description">{member.description}</p>

                {member.links?.length > 0 && (
                  <div className="profile-links">
                    {member.links.map((link) => (
                      <a
                        key={link.label}
                        href={link.href}
                        className="profile-icon-link"
                        title={link.label}
                        aria-label={link.label}
                        target={
                          link.href.startsWith("http") ||
                          link.href.endsWith(".pdf")
                            ? "_blank"
                            : undefined
                        }
                        rel={
                          link.href.startsWith("http") ||
                          link.href.endsWith(".pdf")
                            ? "noreferrer"
                            : undefined
                        }
                      >
                        {icons[link.type] || link.label}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </article>
          </FadeIn>
        ))}
      </section>
    </section>
  );
}

