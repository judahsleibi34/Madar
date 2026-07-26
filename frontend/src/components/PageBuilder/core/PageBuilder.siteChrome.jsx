import { resolveMediaUrl } from "../../../utils/media";
import { defaultSiteChrome } from "./PageBuilder.constants";
import { splitLines } from "./PageBuilder.text";
import {
  getFooterLinkItems,
  getSafeFooterLinkUrl,
  isExternalFooterLink,
} from "./PageBuilder.footerLinks";
import {
  findPageByNavigationReference,
  getNavigablePages,
  getPageNavigationLabel,
} from "./PageBuilder.navigation";

const MADAR_ATTRIBUTION_URL = "https://madar.app/";

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
    const navigateHeaderButton = (event) => {
      event.stopPropagation();

      const targetValue = String(site.headerButtonPageId || site.headerButtonHref || site.headerButtonLabel || "").trim();
      const targetPage = findPageByNavigationReference(project.pages, targetValue);

      if (targetPage) selectPage(targetPage.id);
    };

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
            {getNavigablePages(project.pages, {
              excludePageIds: [
                findPageByNavigationReference(
                  project.pages,
                  site.headerButtonPageId || site.headerButtonHref || site.headerButtonLabel
                )?.id,
              ],
            }).map((page) => (
              <button
                type="button"
                key={page.id}
                className={activePage?.id === page.id ? "active" : ""}
                onClick={(event) => {
                  event.stopPropagation();
                  selectPage(page.id);
                }}
              >
                {getPageNavigationLabel(page)}
              </button>
            ))}
          </nav>

          <button type="button" className="built-site-cta" onClick={navigateHeaderButton}>
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
    const socialLinks = getFooterLinkItems(
      site.footerSocialItems,
      site.footerSocialLinks || "Facebook\nLinkedIn\nX\nInstagram"
    );
    const paymentMethods = getFooterLinkItems(
      site.footerPaymentItems,
      site.footerPaymentMethods || ""
    );
    const footerBrand = site.footerStoreName || site.brand || "Your Brand";
    const footerInitial = footerBrand.trim().slice(0, 1).toUpperCase() || "B";
    const resolveFooterPageLink = (value) => {
      const normalizedValue = String(value || "").toLowerCase().replace(/^\//, "").trim();
      return project.pages.find((page) => {
        const normalizedId = String(page.id || "").toLowerCase();
        const normalizedName = String(page.name || "").toLowerCase().trim();
        const normalizedSlug = String(page.slug || "").toLowerCase().replace(/^\//, "").trim();
        return (
          normalizedId === normalizedValue ||
          normalizedName === normalizedValue ||
          normalizedSlug === normalizedValue ||
          normalizedSlug === normalizedValue.replace(/\s+/g, "-")
        );
      });
    };
    const isVisibleFooterItem = (value) => {
      const normalizedValue = String(value || "").trim();
      return !/^page_[a-z0-9-]{8,}$/i.test(normalizedValue) || Boolean(resolveFooterPageLink(normalizedValue));
    };
    const visiblePageLinks = pageLinks.filter(isVisibleFooterItem);
    const visibleHelpLinks = helpLinks.filter(isVisibleFooterItem);
    const navigateFooterLink = (label) => {
      const target = resolveFooterPageLink(label);

      if (target) selectPage(target.id);
    };

    return (
      <footer
        className={`built-site-footer ecommerce-style-footer ${selected.type === "siteFooter" ? "is-selected" : ""}`}
        onClick={(event) => {
          event.stopPropagation();
          if (!preview) setSelected({ type: "siteFooter", id: "site-footer" });
          if (event.target.closest(".powered-by-madar")) {
            window.location.href = MADAR_ATTRIBUTION_URL;
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
              {socialLinks.map((item) => {
                const href = getSafeFooterLinkUrl(item.url, item.label);
                return href ? (
                  <a
                    href={href}
                    key={`${item.label}-${href}`}
                    aria-label={item.label}
                    target={isExternalFooterLink(href) ? "_blank" : undefined}
                    rel={isExternalFooterLink(href) ? "noopener noreferrer" : undefined}
                    onClick={(event) => {
                      event.stopPropagation();
                      if (!preview) event.preventDefault();
                    }}
                  >
                    {item.label.slice(0, 2).toUpperCase()}
                  </a>
                ) : (
                  <span key={item.label} aria-label={item.label}>{item.label.slice(0, 2).toUpperCase()}</span>
                );
              })}
            </div>

          </div>

          <div className="ecommerce-footer-column ecommerce-footer-pages-column">
            <h4>{site.footerShopTitle || "Pages"}</h4>
            <div className="ecommerce-footer-links-grid">
              {visiblePageLinks.map((item) => <button type="button" key={item} onClick={() => navigateFooterLink(item)}>{resolveFooterPageLink(item)?.name || item}</button>)}
            </div>
          </div>

          <div className="ecommerce-footer-column ecommerce-footer-help-column">
            <h4>{site.footerHelpTitle || "Help"}</h4>
            <div className="ecommerce-footer-links-grid">
              {visibleHelpLinks.map((item) => <button type="button" key={item} onClick={() => navigateFooterLink(item)}>{item}</button>)}
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
            {paymentMethods.length > 0 && (
              <div className="ecommerce-payment-row">
                {paymentMethods.map((item) => {
                  const href = getSafeFooterLinkUrl(item.url, item.label);
                  return href ? (
                    <a
                      href={href}
                      key={`${item.label}-${href}`}
                      target={isExternalFooterLink(href) ? "_blank" : undefined}
                      rel={isExternalFooterLink(href) ? "noopener noreferrer" : undefined}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (!preview) event.preventDefault();
                      }}
                    >
                      {item.label}
                    </a>
                  ) : <span key={item.label}>{item.label}</span>;
                })}
              </div>
            )}
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
