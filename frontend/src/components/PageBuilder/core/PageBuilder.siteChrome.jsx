import {
  Mail,
  Phone,
} from "lucide-react";
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

const MADAR_ATTRIBUTION_URL = "https://madarportal.com/";

const getFooterSocialMark = (label = "") => {
  const value = String(label).toLowerCase();
  if (value.includes("instagram")) return "IG";
  if (value.includes("linkedin")) return "in";
  if (value.includes("youtube")) return "▶";
  if (value.includes("facebook")) return "f";
  if (value.includes("tiktok")) return "TT";
  if (value === "x" || value.includes("twitter")) return "X";
  return "@";
};

export const createSiteChromeRenderers = ({
  project,
  activePage,
  selected,
  preview,
  publicRuntime = false,
  selectPage,
  setSelected,
}) => {
  const renderSiteHeader = () => {
    const site = project.siteChrome || defaultSiteChrome;
    if (!site.showHeader) return null;

    const logoSrc = resolveMediaUrl(site.logoUrl);
    const brandLabel = String(site.brand ?? "").trim();
    const headerButtonLabel = String(site.headerButtonLabel ?? "").trim();
    const headerActionPage = headerButtonLabel
      ? findPageByNavigationReference(
          project.pages,
          site.headerButtonPageId || site.headerButtonHref || headerButtonLabel
        )
      : null;
    const navigablePages = getNavigablePages(project.pages, {
      excludePageIds: [headerActionPage?.id],
    });
    const closeMobileMenu = (event) => {
      event.currentTarget.closest("details")?.removeAttribute("open");
    };
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
            {logoSrc ? <img src={logoSrc} alt={`${brandLabel || "Website"} logo`} /> : brandLabel ? <span className="logo-fallback">{brandLabel.slice(0, 1).toUpperCase()}</span> : null}
            {brandLabel && <span>{brandLabel}</span>}
          </button>

          <nav className="built-site-nav">
            {navigablePages.map((page) => (
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

          {headerButtonLabel && (
            <button type="button" className="built-site-cta" onClick={navigateHeaderButton}>
              {headerButtonLabel}
            </button>
          )}

          {publicRuntime && (
            <details className="built-site-mobile-menu">
              <summary aria-label="Open navigation menu">
                <span aria-hidden="true" />
                <span aria-hidden="true" />
                <span aria-hidden="true" />
              </summary>
              <div className="built-site-mobile-menu-panel">
                {navigablePages.map((page) => (
                  <button
                    type="button"
                    key={page.id}
                    className={activePage?.id === page.id ? "active" : ""}
                    onClick={(event) => {
                      event.stopPropagation();
                      closeMobileMenu(event);
                      selectPage(page.id);
                    }}
                  >
                    {getPageNavigationLabel(page)}
                  </button>
                ))}
                {headerButtonLabel && (
                  <button
                    type="button"
                    className="built-site-mobile-menu-cta"
                    onClick={(event) => {
                      closeMobileMenu(event);
                      navigateHeaderButton(event);
                    }}
                  >
                    {headerButtonLabel}
                  </button>
                )}
              </div>
            </details>
          )}
        </div>
      </header>
    );
  };

  const renderSiteFooter = () => {
    const site = project.siteChrome || defaultSiteChrome;
    if (!site.showFooter) return null;

    const pageLinks = splitLines(site.footerShopLinks || "");
    const helpLinks = splitLines(site.footerHelpLinks || "");
    const socialLinks = getFooterLinkItems(
      site.footerSocialItems,
      site.footerSocialLinks || ""
    );
    const paymentMethods = getFooterLinkItems(
      site.footerPaymentItems,
      site.footerPaymentMethods || ""
    );
    const footerBrand = String(site.footerStoreName ?? "").trim();
    const contactEmail = String(site.contactEmail ?? "").trim();
    const contactPhone = String(site.phone ?? "").trim();
    const footerRights = String(site.rights ?? "").trim();
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
    const visibleQuickLinks = Array.from(new Set([...visiblePageLinks, ...visibleHelpLinks]));
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
              ) : footerBrand ? (
                <div className="ecommerce-footer-logo footer-logo-fallback">{footerInitial}</div>
              ) : null}
              {footerBrand && <h3>{footerBrand}</h3>}
            </div>

            <p>{site.description}</p>

            <div className="ecommerce-social-row">
              {socialLinks.map((item) => {
                const href = getSafeFooterLinkUrl(item.url, item.label);
                const socialMark = getFooterSocialMark(item.label);
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
                    <span className="ecommerce-social-mark" aria-hidden="true">{socialMark}</span>
                  </a>
                ) : (
                  <span key={item.label} aria-label={item.label}><span className="ecommerce-social-mark" aria-hidden="true">{socialMark}</span></span>
                );
              })}
            </div>

          </div>

          <div className="ecommerce-footer-column ecommerce-footer-quick-links">
            <h4>Quick Links</h4>
            <div className="ecommerce-footer-links-grid">
              {visibleQuickLinks.map((item) => <button type="button" key={item} onClick={() => navigateFooterLink(item)}>{resolveFooterPageLink(item)?.name || item}</button>)}
            </div>
          </div>

          <div className="ecommerce-footer-contact">
            <h4>Contact Info</h4>
            {contactEmail && (
              <a className="ecommerce-contact-row" href={`mailto:${contactEmail}`} onClick={(event) => event.stopPropagation()}>
                <Mail size={19} aria-hidden="true" />
                <span>{contactEmail}</span>
              </a>
            )}
            {contactPhone && (
              <a className="ecommerce-contact-row" href={`tel:${contactPhone.replace(/\s+/g, "")}`} dir="ltr" onClick={(event) => event.stopPropagation()}>
                <Phone size={19} aria-hidden="true" />
                <span>{contactPhone}</span>
              </a>
            )}
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
          <p>© 2026{footerBrand ? ` ${footerBrand}.` : ""}{footerRights ? ` ${footerRights}` : ""}</p>
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
