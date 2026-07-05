import FadeIn from "../Animations/FadeIn";
import GradientText from "../Animations/GradientText";
import { getTeamContent } from "../../content";

const icons = {
  linkedin: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4.98 3.5C4.98 4.88 3.86 6 2.5 6S0 4.88 0 3.5 1.12 1 2.5 1s2.48 1.12 2.48 2.5ZM.4 8h4.2v15H.4V8Zm7.1 0h4v2.05h.06c.56-1.06 1.94-2.18 3.99-2.18 4.27 0 5.05 2.81 5.05 6.46V23h-4.2v-7.67c0-1.83-.03-4.18-2.55-4.18-2.55 0-2.94 1.99-2.94 4.05V23H7.5V8Z" />
    </svg>
  ),
  github: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.09 3.29 9.39 7.86 10.91.58.1.79-.25.79-.56v-2.15c-3.2.7-3.87-1.37-3.87-1.37-.52-1.32-1.28-1.67-1.28-1.67-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.23-1.28-5.23-5.68 0-1.25.45-2.28 1.18-3.08-.12-.29-.51-1.46.11-3.04 0 0 .96-.31 3.15 1.18A10.9 10.9 0 0 1 12 6.07c.97 0 1.94.13 2.85.38 2.18-1.49 3.14-1.18 3.14-1.18.62 1.58.23 2.75.11 3.04.74.8 1.18 1.83 1.18 3.08 0 4.42-2.69 5.38-5.25 5.67.41.36.78 1.06.78 2.13v3.16c0 .31.21.67.8.56A11.52 11.52 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z" />
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
  phone: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6.6 2.5 10 6l-2.1 2.1c.9 1.8 2.2 3.5 3.7 5s3.2 2.8 5 3.7L18.7 15l3.3 3.4-1.6 3.1c-.4.8-1.3 1.2-2.1 1C9.8 20.6 3.4 14.2 1.5 5.7c-.2-.9.2-1.7 1-2.1l4.1-1.1Z" />
    </svg>
  ),
};

export default function TeamPage({ lang = "en" }) {
  const t = getTeamContent(lang);

  return (
    <main className="team-page">
      <FadeIn>
        <section className="team-hero">
          <h1><GradientText pauseOnHover>{t.title}</GradientText></h1>
          <p>{t.subtitle}</p>
        </section>
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
                <h2>{member.name}</h2>
                <p className="profile-role"><GradientText pauseOnHover>{member.role}</GradientText></p>
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
    </main>
  );
}

