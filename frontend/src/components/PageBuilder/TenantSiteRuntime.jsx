import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import ForgotPasswordPage from "../AuthPages/ForgotPasswordPage";
import LoginPage from "../AuthPages/LoginPage";
import SignUpPage from "../AuthPages/SignUpPage";
import { STORAGE_KEY, defaultSiteChrome, fieldTypes, viewports } from "./PageBuilder.constants";
import { getFormSections } from "./PageBuilder.factories";
import "../../styles/admin/PageBuilder/PageBuilder.css";
import PageBuilderCarousel from "./PageBuilderCarousel";

const splitLines = (value) =>
  String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

const carouselElementTypes = new Set(["carousel", "carouselCards", "carouselSplit", "circularGallery"]);

const getFieldType = (type) => fieldTypes.find((item) => item.id === type) || fieldTypes[0];

const getModernFieldPlaceholder = (field = {}) => {
  const customPlaceholder = String(field.placeholder || "").trim();
  const genericPlaceholders = new Set([
    "",
    "Short answer",
    "Paragraph",
    "Email",
    "Phone number",
    "Website URL",
    "Number",
    "Money amount",
    "Date",
    "Time",
    "Dropdown",
    "Single choice",
    "Checkboxes",
    "Yes / No",
    "Linear scale",
    "Rating",
    "Status",
    "File upload",
  ]);

  if (!genericPlaceholders.has(customPlaceholder)) return customPlaceholder;

  const label = String(field.label || "").toLowerCase();

  if (field.type === "email" || label.includes("email")) return "name@company.com";
  if (field.type === "phone" || label.includes("phone")) return "+972 50 123 4567";
  if (field.type === "url" || label.includes("website")) return "https://yourcompany.com";
  if (field.type === "money" || label.includes("budget") || label.includes("amount")) return "Example: 7,500";
  if (field.type === "number" || label.includes("size")) return "Example: 12";
  if (field.type === "date") return "Select a date";
  if (field.type === "time") return "Select a time";
  if (field.type === "dropdown" || field.type === "status") return "Select an option";
  if (field.type === "radio") return "Choose one option";
  if (field.type === "checkboxes") return "Select all that apply";
  if (field.type === "paragraph" || label.includes("summary") || label.includes("details")) {
    return "Briefly describe what you need...";
  }
  if (label.includes("name")) return "e.g. Sarah Haddad";

  return "Type your answer";
};

const normalizeElementAlignSelf = (value) => {
  if (!value || value === "auto") return undefined;
  if (value === "left") return "flex-start";
  if (value === "right") return "flex-end";
  return value;
};

const getElementLayoutWidth = (value, alignSelf = "auto") => {
  const placement = normalizeElementAlignSelf(alignSelf);

  if (placement === "stretch") return "100%";

  if (!value || value === "auto") return undefined;
  return value;
};

const getComponentPositionClass = (position) => {
  const normalized = normalizeElementAlignSelf(position);
  if (position === "Left" || normalized === "flex-start") return "justify-start";
  if (position === "Center" || normalized === "center") return "justify-center";
  if (position === "Right" || normalized === "flex-end") return "justify-end";
  return "justify-center";
};

const getCarouselWidthValue = (element) => {
  const width = element.styles?.width;
  if (!width || width === "auto") return "100%";
  return width;
};

const getElementPlacementMargins = (value) => {
  const placement = normalizeElementAlignSelf(value);

  if (placement === "center") {
    return { marginLeft: "auto", marginRight: "auto" };
  }

  if (placement === "flex-end") {
    return { marginLeft: "auto", marginRight: "0" };
  }

  if (placement === "flex-start") {
    return { marginLeft: "0", marginRight: "auto" };
  }

  return { marginLeft: undefined, marginRight: undefined };
};

const getCarouselVariant = (element) => {
  if (element.carouselVariant) return element.carouselVariant;
  if (element.type === "carouselCards") return "cards";
  if (element.type === "carouselSplit") return "split";
  if (element.type === "circularGallery") return "circular";
  return "lightswind";
};

const getRowCarouselElements = (row) =>
  (row.columns || []).flatMap((column) =>
    (column.elements || []).filter((element) => carouselElementTypes.has(element.type))
  );

const getCleanSubdomain = (value = "") =>
  String(value)
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "") || "my-site";

const loadPublishedProject = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const getScreenViewport = () => {
  if (typeof window === "undefined") return "desktop";
  if (window.innerWidth <= viewports.mobile) return "mobile";
  if (window.innerWidth <= viewports.tablet) return "tablet";
  return "desktop";
};

export default function TenantSiteRuntime() {
  const params = useParams();
  const { subdomain = "my-site" } = params;
  const location = useLocation();
  const navigate = useNavigate();

  const cleanSubdomain = getCleanSubdomain(subdomain);
  const [runtimeViewport, setRuntimeViewport] = useState(getScreenViewport);

  const project = useMemo(() => loadPublishedProject(), []);
  const site = {
    ...defaultSiteChrome,
    ...(project?.siteChrome || {}),
    headerButtonLabel: "Login",
  };

  const pages = useMemo(() => project?.pages || [], [project?.pages]);
  const activePath = location.pathname;
  const isLoginPage = activePath.endsWith("/login");
  const isSignupPage = activePath.endsWith("/signup");
  const isForgotPasswordPage = activePath.endsWith("/forgot-password");
  const isDashboardPage = activePath.endsWith("/dashboard");
  const pagePath = `/${params["*"] || ""}`;

  const siteHomePath = `/site/${cleanSubdomain}`;
  const loginPath = `/site/${cleanSubdomain}/login`;
  const signupPath = `/site/${cleanSubdomain}/signup`;
  const forgotPasswordPath = `/site/${cleanSubdomain}/forgot-password`;
  const dashboardPath = `/site/${cleanSubdomain}/dashboard`;

  const pageLinks = splitLines(site.footerShopLinks || "Home\nSubmit Request\nReports");
  const helpLinks = splitLines(site.footerHelpLinks || "About Us\nPolicies\nContact");
  const socialLinks = splitLines(site.footerSocialLinks || "Facebook\nLinkedIn\nX\nInstagram");
  const footerLinks = [...pageLinks, ...helpLinks];

  const brandName = site.brand || "Madar";
  const footerBrand = site.footerStoreName || brandName;
  const footerInitial = footerBrand.trim().slice(0, 1).toUpperCase() || "M";

  const goToPage = (page) => {
    if (!page) {
      navigate(siteHomePath);
      return;
    }

    const slug = page.slug === "/" ? "" : page.slug;
    navigate(`/site/${cleanSubdomain}${slug}`);
  };

  const goToFooterLink = (label) => {
    const normalizedLabel = label.toLowerCase().trim();

    const target = pages.find((page) => {
      const normalizedName = String(page.name || "").toLowerCase().trim();
      const normalizedSlug = String(page.slug || "")
        .toLowerCase()
        .replace(/^\//, "");

      return (
        normalizedName === normalizedLabel ||
        normalizedSlug === normalizedLabel.replace(/\s+/g, "-")
      );
    });

    if (target) {
      goToPage(target);
      return;
    }

    if (normalizedLabel === "home") {
      navigate(siteHomePath);
      return;
    }

    if (normalizedLabel === "login") {
      navigate(loginPath);
    }
  };

  const activePage = useMemo(() => {
    const normalizedPath = pagePath === "/" ? "/" : pagePath.replace(/\/+$/, "");
    return (
      pages.find((page) => page.slug === normalizedPath) ||
      pages.find((page) => page.slug === "/" && normalizedPath === "/") ||
      pages[0]
    );
  }, [pagePath, pages]);

  useEffect(() => {
    const syncViewport = () => setRuntimeViewport(getScreenViewport());
    syncViewport();
    window.addEventListener("resize", syncViewport);
    return () => window.removeEventListener("resize", syncViewport);
  }, []);

  const getElementStyle = (element, isFree = false, section = null) => {
    if (isFree) {
      const position = element.position?.[runtimeViewport] || element.position?.desktop || {};
      const viewportWidth = viewports[runtimeViewport] || viewports.desktop;
      const sectionHeight = Number(section?.layout?.minHeight) || 560;
      const left = `${((Number(position.x) || 0) / viewportWidth) * 100}%`;
      const top = `${((Number(position.y) || 0) / sectionHeight) * 100}%`;
      const width = `${((Number(position.width) || 240) / viewportWidth) * 100}%`;
      const minHeight = `${((Number(position.height) || 80) / sectionHeight) * 100}%`;

      return {
        ...element.styles,
        "--builder-element-color": element.styles?.color || "inherit",
        "--builder-element-bg": element.styles?.backgroundColor || "transparent",
        "--builder-element-radius": element.styles?.borderRadius || "0",
        "--builder-element-font-size": element.styles?.fontSize || "inherit",
        "--builder-element-text-align": element.styles?.textAlign || "inherit",
        position: "absolute",
        left,
        top,
        width,
        minHeight,
        maxWidth: `calc(100% - ${left})`,
      };
    }
    const placementMargins = getElementPlacementMargins(element.styles?.alignSelf);
    const layoutWidth =
      getElementLayoutWidth(element.styles?.width, element.styles?.alignSelf) ||
      (carouselElementTypes.has(element.type) ? "100%" : undefined);

    return {
      ...element.styles,
      "--builder-element-width": layoutWidth || "auto",
      "--builder-element-align": normalizeElementAlignSelf(element.styles?.alignSelf) || "auto",
      "--builder-element-color": element.styles?.color || "inherit",
      "--builder-element-bg": element.styles?.backgroundColor || "transparent",
      "--builder-element-radius": element.styles?.borderRadius || "0",
      "--builder-element-font-size": element.styles?.fontSize || "inherit",
      "--builder-element-text-align": element.styles?.textAlign || "inherit",
      position: "relative",
      transform: undefined,
      width: layoutWidth,
      minHeight: element.styles?.minHeight || undefined,
      maxWidth: "100%",
      alignSelf: normalizeElementAlignSelf(element.styles?.alignSelf),
      ...placementMargins,
    };
  };

  const renderConnectedForm = (formId) => {
    const form = project?.forms?.find((item) => item.id === formId) || project?.forms?.[0];
    if (!form) return <div className="empty-connected">No form selected.</div>;

    const renderReadOnlyField = (field) => {
      const meta = getFieldType(field.type);
      const placeholder = getModernFieldPlaceholder(field);

      if (meta.input === "textarea") {
        return <textarea placeholder={placeholder} readOnly />;
      }

      return <input type="text" placeholder={placeholder} readOnly />;
    };

    return (
      <div className="runtime-form">
        <div className="runtime-form-header">
          <h3>{form.title}</h3>
          <p>{form.description}</p>
        </div>

        {getFormSections(form).map((section) => (
          <div className="runtime-form-section" key={section.id}>
            <div className="runtime-form-section-header">
              <h4>{section.title}</h4>
              {section.description && <p>{section.description}</p>}
            </div>

            {(section.fields || []).map((field) => (
              <div className="runtime-question" key={field.id}>
                <label>
                  <span>
                    {field.label}
                    {field.required ? " *" : ""}
                  </span>
                  {field.helpText && <small>{field.helpText}</small>}
                  {renderReadOnlyField(field)}
                </label>
              </div>
            ))}
          </div>
        ))}

        <button type="button" className="runtime-submit">
          Submit
        </button>
      </div>
    );
  };

  const renderResponsesTable = (formId) => {
    const form = project?.forms?.find((item) => item.id === formId) || project?.forms?.[0];
    if (!form) return <div className="empty-connected">No form selected.</div>;

    const fields = (form.sections || [])
      .flatMap((section) => section.fields || [])
      .slice(0, 4);
    const responses = form.responses || [];

    return (
      <div className="responses-preview">
        <div className="responses-preview-header">
          <strong>{form.title}</strong>
          <span>{responses.length} responses</span>
        </div>

        <div className="mock-table">
          <div className="mock-table-row mock-table-head">
            <span>Status</span>
            {fields.map((field) => (
              <span key={field.id}>{field.label}</span>
            ))}
          </div>

          {(responses.length ? responses : [{ id: "sample", status: "Sample", answers: {} }]).map((response) => (
            <div className="mock-table-row" key={response.id}>
              <span>{response.status || "New"}</span>
              {fields.map((field) => (
                <span key={field.id}>{response.answers?.[field.id] || "-"}</span>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderElement = (element, isFree = false, section = null) => {
    const props = {
      className: `builder-element builder-element-${element.type}`,
      style: getElementStyle(element, isFree, section),
    };

    if (element.type === "heading") return <h1 key={element.id} {...props}>{element.content}</h1>;
    if (element.type === "text") return <p key={element.id} {...props}>{element.content}</p>;
    if (element.type === "button") return <button key={element.id} type="button" {...props}>{element.content}</button>;
    if (element.type === "image") return <img key={element.id} {...props} src={element.content} alt={element.name || ""} />;
    if (element.type === "card") {
      return (
        <div key={element.id} {...props}>
          {String(element.content || "").split("\n").map((line, index) => (
            <span key={`${element.id}_${index}`}>{line}</span>
          ))}
        </div>
      );
    }
    if (carouselElementTypes.has(element.type)) {
      const carouselWidth = getCarouselWidthValue(element);
      const carouselFrameStyle = {
        ...props.style,
        width: "100%",
        maxWidth: "100%",
        alignSelf: "stretch",
        marginLeft: undefined,
        marginRight: undefined,
        "--builder-element-width": "100%",
        "--builder-element-align": "stretch",
      };

      return (
        <div
          key={element.id}
          {...props}
          className={`${props.className} carousel-position-frame ${getComponentPositionClass(element.styles?.alignSelf)}`}
          style={carouselFrameStyle}
        >
          <div
            className="carousel-position-inner"
            style={{ width: carouselWidth, maxWidth: carouselWidth }}
          >
            <PageBuilderCarousel
              autoScroll={Boolean(element.autoScroll)}
              autoScrollMs={element.autoScrollMs}
              content={element.content}
              name={element.name}
              variant={getCarouselVariant(element)}
            />
          </div>
        </div>
      );
    }
    if (element.type === "list") {
      return (
        <ul key={element.id} {...props}>
          {splitLines(element.content).map((item) => <li key={item}>{item}</li>)}
        </ul>
      );
    }
    if (element.type === "divider") return <hr key={element.id} {...props} />;
    if (element.type === "embed") {
      return (
        <div key={element.id} {...props}>
          <strong>Embed</strong>
          <a href={element.content} target="_blank" rel="noreferrer">{element.content}</a>
        </div>
      );
    }
    if (element.type === "metric") {
      const [label, value] = String(element.content || "").split("\n");
      return (
        <div key={element.id} {...props}>
          <span className="metric-label">{label}</span>
          <strong className="metric-value">{value}</strong>
        </div>
      );
    }
    if (element.type === "formBlock") return <div key={element.id} {...props}>{renderConnectedForm(element.connectedFormId)}</div>;
    if (element.type === "responsesTable") return <div key={element.id} {...props}>{renderResponsesTable(element.connectedFormId)}</div>;

    return <div key={element.id} {...props}>{element.content}</div>;
  };

  const renderPublishedPage = () => {
    if (!project || !activePage) {
      return (
        <main className="tenant-runtime-main">
          <section className="tenant-runtime-card">
            <p className="tenant-eyebrow">{cleanSubdomain}.madar.app</p>
            <h1>No published site found</h1>
            <p>Save the project in Page Builder, then use Go Live again.</p>
          </section>
        </main>
      );
    }

    return (
      <main className="tenant-runtime-page">
        <div className={`builder-canvas viewport-${runtimeViewport}`}>
          {(activePage.sections || []).map((section) => {
            if (section.mode === "free") {
              return (
                <section
                  key={section.id}
                  className={`site-section free-canvas-section width-${section.layout.width}`}
                  style={{ backgroundColor: section.layout.background, minHeight: section.layout.minHeight }}
                >
                  <div
                    className="free-canvas-frame"
                    style={{
                      width: `min(100%, ${viewports[runtimeViewport] || viewports.desktop}px)`,
                      minHeight: `${section.layout.minHeight}px`,
                    }}
                  >
                    {(section.freeElements || []).map((element) => renderElement(element, true, section))}
                  </div>
                </section>
              );
            }

            return (
              <section
                key={section.id}
                className={`site-section width-${section.layout.width} padding-${section.layout.paddingY}`}
                style={{ backgroundColor: section.layout.background }}
              >
                {(section.rows || []).map((row) => (
                  <div
                    key={row.id}
                    className={`site-row columns-${row.layout.columns} align-${row.layout.align} gap-${row.layout.gap}`}
                  >
                    {(row.columns || []).map((column) => (
                      <div
                        key={column.id}
                        className={`site-column column-align-${column.layout.align}`}
                      >
                        {(column.elements || [])
                          .filter((element) => !carouselElementTypes.has(element.type))
                          .map((element) => renderElement(element, false))}
                      </div>
                    ))}
                    {getRowCarouselElements(row).map((element) => renderElement(element, false))}
                  </div>
                ))}
              </section>
            );
          })}
        </div>
      </main>
    );
  };

  const renderHeader = () => (
    <header className="tenant-site-header">
      <div className="tenant-site-header-inner">
        <button
          type="button"
          className="tenant-site-brand"
          onClick={() => navigate(siteHomePath)}
        >
          {site.logoUrl ? (
            <img src={site.logoUrl} alt={`${brandName} logo`} />
          ) : (
            <span className="tenant-logo-fallback">
              {brandName.slice(0, 1).toUpperCase() || "M"}
            </span>
          )}

          <span>{brandName}</span>
        </button>

        <nav className="tenant-site-nav">
          {pages.map((page) => {
            const pagePath =
              page.slug === "/"
                ? siteHomePath
                : `/site/${cleanSubdomain}${page.slug}`;

            return (
              <button
                type="button"
                key={page.id}
                className={activePath === pagePath ? "active" : ""}
                onClick={() => goToPage(page)}
              >
                {page.name}
              </button>
            );
          })}
        </nav>

        <button
          type="button"
          className="tenant-site-cta"
          onClick={() => navigate(loginPath)}
        >
          Login
        </button>
      </div>
    </header>
  );

  const renderFooter = () => (
    <footer className="tenant-site-footer">
      <div className="tenant-footer-grid">
        <div className="tenant-footer-brand">
          <div className="tenant-footer-logo-row">
            {site.logoUrl ? (
              <img
                className="tenant-footer-logo"
                src={site.logoUrl}
                alt={`${footerBrand} logo`}
              />
            ) : (
              <div className="tenant-footer-logo tenant-footer-logo-fallback">
                {footerInitial}
              </div>
            )}

            <h3>{footerBrand}</h3>
          </div>

          <p>
            {site.description ||
              "An adaptive business management platform for creating and managing digital systems."}
          </p>

          <div className="tenant-social-row">
            {socialLinks.map((item) => (
              <button type="button" key={item} aria-label={item}>
                {item.slice(0, 2).toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <div className="tenant-footer-column">
          <h4>Links</h4>

          <div className="tenant-footer-links-grid">
            {footerLinks.map((item) => (
              <button
                type="button"
                key={item}
                onClick={() => goToFooterLink(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="tenant-footer-contact">
          <h4>Contact</h4>

          <div className="tenant-language-pill">
            <span>◎</span>
            <strong>{site.footerLanguageLabel || "AR"}</strong>
          </div>

          <p>{site.contactEmail || "info@madar.com"}</p>
          <p dir="ltr">{site.phone || "+972599203857"}</p>
        </div>
      </div>

      <div className="tenant-footer-bottom">
        <p>
          © 2026 {footerBrand}. {site.rights || "All rights reserved."}
        </p>

        <button type="button" onClick={() => navigate("/")}>
          Powered by Madar
        </button>
      </div>
    </footer>
  );

  const renderMainContent = () => {
    if (isLoginPage) {
      return (
        <main className="tenant-login-runtime">
          <LoginPage
            lang="en"
            signupPath={signupPath}
            forgotPasswordPath={forgotPasswordPath}
            onLoginSuccess={() => navigate(dashboardPath, { replace: true })}
          />
        </main>
      );
    }

    if (isSignupPage) {
      return (
        <main className="tenant-login-runtime">
          <SignUpPage
            lang="en"
            loginPath={loginPath}
            onSignupSuccess={() => navigate(loginPath, { replace: true })}
          />
        </main>
      );
    }

    if (isForgotPasswordPage) {
      return (
        <main className="tenant-login-runtime">
          <ForgotPasswordPage lang="en" />
        </main>
      );
    }

    if (isDashboardPage) {
      return (
        <main className="tenant-runtime-main">
          <section className="tenant-runtime-card">
            <p className="tenant-eyebrow">{cleanSubdomain}.madar.app</p>
            <h1>Website workspace</h1>
            <p>
              This is the private workspace for this website. Later, this page
              will show internal dashboards, forms, responses, and team tools.
            </p>

            <div className="tenant-runtime-actions">
              <button type="button" onClick={() => navigate(siteHomePath)}>
                Open website
              </button>

              <button type="button" onClick={() => navigate(loginPath)}>
                Open login page
              </button>
            </div>
          </section>
        </main>
      );
    }

    return renderPublishedPage();
  };

  return (
    <div className="tenant-site-runtime">
      {renderHeader()}
      {renderMainContent()}
      {renderFooter()}
    </div>
  );
}
