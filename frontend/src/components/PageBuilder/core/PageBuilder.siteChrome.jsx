import { resolveMediaUrl } from "../../../utils/media";
import { defaultSiteChrome } from "./PageBuilder.constants";
import { splitLines } from "./PageBuilder.text";

export const createSiteChromeRenderers = ({
  project,
  activePage,
  selected,
  preview,
  selectPage,
  setSelected,
}) => {
  const renderSiteHeader = () => {
    const site = project.siteChrome || defaultSiteChrome;
    if (!site.showHeader) return null;

    const logoSrc = resolveMediaUrl(site.logoUrl);

    return (
      <header
        className={`built-site-header header-align-${site.headerAlign || "center"} ${selected.type === "siteHeader" ? "is-selected" : ""}`}
        onClick={(event) => {
          event.stopPropagation();
          if (!preview) setSelected({ type: "siteHeader", id: "site-header" });
        }}
      >
        <div className="built-site-header-inner">
          <button
            type="button"
            className="built-site-brand"
            onClick={(event) => {
              event.stopPropagation();
              const homePage = project.pages.find((page) => page.slug === "/") || project.pages[0];
              if (homePage) selectPage(homePage.id);
            }}
          >
            {logoSrc ? <img src={logoSrc} alt={`${site.brand || "Website"} logo`} /> : <span className="logo-fallback">M</span>}
            <span>{site.brand || "Website"}</span>
          </button>

          <nav className="built-site-nav">
            {project.pages.map((page) => (
              <button
                type="button"
                key={page.id}
                className={activePage?.id === page.id ? "active" : ""}
                onClick={(event) => {
                  event.stopPropagation();
                  selectPage(page.id);
                }}
              >
                {page.name}
              </button>
            ))}
          </nav>

          <button type="button" className="built-site-cta">
            {site.headerButtonLabel || "Contact"}
          </button>
        </div>
      </header>
    );
  };

  const renderSiteFooter = () => {
    const site = project.siteChrome || defaultSiteChrome;
    if (!site.showFooter) return null;

    const pageLinks = splitLines(site.footerShopLinks || "");
    const helpLinks = splitLines(site.footerHelpLinks || "About Us\nPolicies\nContact");
    const socialLinks = splitLines(site.footerSocialLinks || "Facebook\nLinkedIn\nX\nInstagram");
    const footerLinks = [...pageLinks, ...helpLinks];
    const footerBrand = site.footerStoreName || site.brand || "Your Brand";
    const footerInitial = footerBrand.trim().slice(0, 1).toUpperCase() || "B";
    const navigateFooterLink = (label) => {
      const normalizedLabel = label.toLowerCase().trim();
      const target = project.pages.find((page) => {
        const normalizedName = page.name.toLowerCase().trim();
        const normalizedSlug = page.slug.toLowerCase().replace(/^\//, "");
        return normalizedName === normalizedLabel || normalizedSlug === normalizedLabel.replace(/\s+/g, "-");
      });

      if (target) selectPage(target.id);
    };

    return (
      <footer
        className={`built-site-footer ecommerce-style-footer ${selected.type === "siteFooter" ? "is-selected" : ""}`}
        onClick={(event) => {
          event.stopPropagation();
          if (!preview) setSelected({ type: "siteFooter", id: "site-footer" });
          if (event.target.closest(".powered-by-madar")) {
            window.location.href = site.madarLink || "/";
          }
        }}
      >
        <div className="ecommerce-footer-grid">
          <div className="ecommerce-footer-brand">
            <div className="ecommerce-footer-logo-row">
              {resolveMediaUrl(site.logoUrl) ? (
                <img className="ecommerce-footer-logo" src={resolveMediaUrl(site.logoUrl)} alt={`${footerBrand} logo`} />
              ) : (
                <div className="ecommerce-footer-logo footer-logo-fallback">{footerInitial}</div>
              )}
              <h3>{footerBrand}</h3>
            </div>

            <p>{site.description}</p>

            <div className="ecommerce-social-row">
              {socialLinks.map((item) => (
                <button type="button" key={item} aria-label={item}>
                  {item.slice(0, 2).toUpperCase()}
                </button>
              ))}
            </div>

          </div>

          <div className="ecommerce-footer-column ecommerce-footer-links-column">
            <h4>Links</h4>
            <div className="ecommerce-footer-links-grid">
              {footerLinks.map((item) => <button type="button" key={item} onClick={() => navigateFooterLink(item)}>{item}</button>)}
            </div>
          </div>

          <div className="ecommerce-footer-contact">
            <h4>Contact</h4>
            <div className="footer-language-pill">
              <span>|</span>
              <strong>{site.footerLanguageLabel || "AR"}</strong>
            </div>
            <p>{site.contactEmail || "info@madar.com"}</p>
            <p dir="ltr">{site.phone || "+972599203857"}</p>
          </div>
        </div>

        <div className="ecommerce-footer-bottom">
          <p>(c) 2026 {site.footerStoreName || site.brand || "Your Website"}. {site.rights || "All rights reserved."}</p>
          <button type="button" className="powered-by-madar">Powered by Madar</button>
        </div>
      </footer>
    );
  };

  return {
    renderSiteHeader,
    renderSiteFooter,
  };
};
