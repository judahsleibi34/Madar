import {
  Mail,
  Phone,
} from "lucide-react";
import { getResponsiveMediaProps } from "../../../utils/media";
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

    const headerBackgroundColor = /^#[0-9a-f]{6}$/i.test(String(site.headerBackgroundColor || ""))
      ? site.headerBackgroundColor
      : "";
    const logoProps = getResponsiveMediaProps(site.logoUrl, {
      widths: [320, 480],
      fallbackWidth: 480,
      sizes: "240px",
    });
    const logoSrc = logoProps.src;
    const logoWidth = Math.min(240, Math.max(16, Number(site.logoWidth) || defaultSiteChrome.logoWidth));
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
        style={{
          ...(headerBackgroundColor ? { backgroundColor: headerBackgroundColor } : {}),
          ['--site-header-logo-width']: `${logoWidth}px`,
        }}
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
            {logoSrc ? <img {...logoProps} alt={`${brandLabel || "Website"} logo`} /> : brandLabel ? <span className="logo-fallback">{brandLabel.slice(0, 1).toUpperCase()}</span> : null}
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
    const footerDescription = String(site.description ?? "").trim();
    const footerShopTitle = String(site.footerShopTitle ?? "").trim() || "Pages";
    const footerHelpTitle = String(site.footerHelpTitle ?? "").trim() || "Help";
    const footerLogoProps = getResponsiveMediaProps(site.logoUrl, {
      widths: [320, 480],
      fallbackWidth: 480,
      sizes: "160px",
    });
    const hasBrandSection = Boolean(footerLogoProps.src || footerBrand || footerDescription || socialLinks.length);
    const hasContactDetails = Boolean(contactEmail || contactPhone);
    const hasContactSection = Boolean(hasContactDetails || paymentMethods.length);
    const footerSectionCount = [
      hasBrandSection,
      visiblePageLinks.length > 0,
      visibleHelpLinks.length > 0,
      hasContactSection,
    ].filter(Boolean).length;
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
        }}
      >
        {footerSectionCount > 0 && (
        <div className="ecommerce-footer-grid" data-section-count={footerSectionCount}>
          {hasBrandSection && <div className="ecommerce-footer-brand">
            <div className="ecommerce-footer-logo-row">
              {footerLogoProps.src ? (
                <img className="ecommerce-footer-logo" {...footerLogoProps} alt={footerBrand ? `${footerBrand} logo` : "Footer logo"} />
              ) : footerBrand ? (
                <div className="ecommerce-footer-logo footer-logo-fallback">{footerInitial}</div>
              ) : null}
              {footerBrand && <h3>{footerBrand}</h3>}
            </div>

            {footerDescription && <p>{footerDescription}</p>}

            {socialLinks.length > 0 && <div className="ecommerce-social-row">
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
            </div>}

          </div>}

          {visiblePageLinks.length > 0 && <div className="ecommerce-footer-column ecommerce-footer-quick-links">
            <h4>{footerShopTitle}</h4>
            <div className="ecommerce-footer-links-grid">
              {visiblePageLinks.map((item) => <button type="button" key={item} onClick={() => navigateFooterLink(item)}>{resolveFooterPageLink(item)?.name || item}</button>)}
            </div>
          </div>}

          {visibleHelpLinks.length > 0 && <div className="ecommerce-footer-column ecommerce-footer-quick-links">
            <h4>{footerHelpTitle}</h4>
            <div className="ecommerce-footer-links-grid">
              {visibleHelpLinks.map((item) => <button type="button" key={item} onClick={() => navigateFooterLink(item)}>{resolveFooterPageLink(item)?.name || item}</button>)}
            </div>
          </div>}

          {hasContactSection && <div className="ecommerce-footer-contact">
            <h4>{hasContactDetails ? "Contact Info" : "Payment Methods"}</h4>
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
          </div>}
        </div>
        )}

        <div className="ecommerce-footer-bottom">
          <p>© 2026{footerBrand ? ` ${footerBrand}.` : ""}{footerRights ? ` ${footerRights}` : ""}</p>
          <a href={MADAR_ATTRIBUTION_URL} className="powered-by-madar" onClick={(event) => event.stopPropagation()}>Powered by Madar</a>
        </div>
      </footer>
    );
  };

  return {
    renderSiteHeader,
    renderSiteFooter,
  };
};
