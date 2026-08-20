import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Clock3,
  KeyRound,
  Loader2,
  LockKeyhole,
  Mail,
  Search,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";
import { apiFetch, getApiUrl, readApiError, readApiResponse } from "../../utils/apiClient";

function normalizeAccessCode(value) {
  return value.replace(/[^A-Za-z0-9!@#$%&*?]/g, "").slice(0, 6);
}

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

const USER_SEARCH_CACHE_TTL_MS = 60 * 1000;
const ACCOUNT_ACCESS_UNAVAILABLE_MESSAGE =
  "Account access is temporarily unavailable. Please try again later.";

function isRegularUserAccount(user) {
  const role = String(
    user?.user_type ||
      user?.role ||
      user?.type ||
      user?.account_type ||
      ""
  )
    .trim()
    .toLowerCase();

  return role !== "admin" && role !== "administrator" && role !== "super_admin";
}

function readAccountAccessError(response, data, fallback) {
  const code =
    data?.code ||
    data?.detail?.code ||
    data?.error?.code ||
    "";

  if (
    response.status === 503 ||
    code === "admin_account_access_not_ready"
  ) {
    return ACCOUNT_ACCESS_UNAVAILABLE_MESSAGE;
  }

  return readApiError(data, fallback);
}

function formatAccessExpiry(value) {
  if (!value) return "10 minutes";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "10 minutes";
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getDeliverySummary(accessRequest) {
  if (accessRequest?.delivery === "development_log") {
    return {
      title: "Permission code generated",
      detail: "SMTP is not configured. Check the backend logs for the development code.",
      deliveryLabel: "Development log",
    };
  }

  return {
    title: "Permission code sent",
    detail: "Ask the user to share the code they received.",
    deliveryLabel: "Email",
  };
}

export default function AdminAccountAccessPage({
  lang = "en",
  themeMode = "light",
  currentUser,
}) {
  const isRtl = lang === "ar";

  const copy = useMemo(() => {
    if (isRtl) {
      return {
        eyebrow: "وصول المسؤول",
        title: "الدخول إلى حساب مستخدم بإذن",
        subtitle:
          "أدخل بريد المستخدم لتوليد رمز إذن. بعد أن يستلم المستخدم الرمز ويرسله لك، أدخل الرمز للدخول إلى حسابه بشكل مؤقت وآمن.",
        emailTitle: "توليد رمز الإذن",
        emailLabel: "بريد المستخدم",
        emailPlaceholder: "user@example.com",
        generateCode: "توليد الرمز",
        generating: "جاري التوليد...",
        codeSent:
          "تم إرسال رمز الإذن إلى المستخدم. اطلب منه إرسال الرمز لك للمتابعة.",
        codeTitle: "إدخال رمز الإذن",
        codeLabel: "رمز الإذن",
        codePlaceholder: "000000",
        codeHelper: "يجب أن يكون الرمز مكونًا من 6 أرقام.",
        accessAccount: "الدخول إلى الحساب",
        accessing: "جاري الدخول...",
        invalidEmail: "أدخل بريدًا إلكترونيًا صحيحًا.",
        invalidCode: "أدخل رمزًا صحيحًا من 6 أرقام.",
        missingEmailFirst: "قم بتوليد الرمز أولًا قبل إدخال رمز الإذن.",
        accessReady:
          "تم التحقق من الرمز. اربط هذه الخطوة لاحقًا بتحويل المسؤول إلى جلسة المستخدم.",
        consentTitle: "موافقة المستخدم مطلوبة",
        consentText:
          "لا يمكن للمسؤول الدخول إلا بعد أن يشارك المستخدم رمز الإذن. يجب تسجيل هذا الإجراء في النظام.",
        securityTitle: "ملاحظة أمنية",
        securityText:
          "يجب أن يكون الرمز مؤقتًا، أحادي الاستخدام، ومتحققًا من الخادم فقط.",
        activityTitle: "آخر إجراءات الوصول",
        noActivity: "لا توجد إجراءات وصول حديثة.",
      };
    }

    return {
      eyebrow: "Admin Access",
      title: "Access a user account with permission",
      subtitle:
        "Enter the user email to generate a permission code. After the user receives the code and sends it back to you, enter the 6-character code to access their account temporarily and securely.",
      emailTitle: "Generate permission code",
      emailLabel: "User email",
      emailPlaceholder: "user@example.com",
      generateCode: "Generate code",
      generating: "Generating...",
      codeSent:
        "Permission code sent to the user. Ask the user to send the code back to continue.",
      codeTitle: "Enter permission code",
      codeLabel: "Permission code",
      codePlaceholder: "A7!k9Q",
      codeHelper: "The code must be exactly 6 characters.",
      accessAccount: "Access account",
      accessing: "Accessing...",
      invalidEmail: "Enter a valid email address.",
      invalidCode: "Enter a valid 6-character code.",
      missingEmailFirst: "Generate the code first before entering permission code.",
      accessReady:
        "Code verified. Opening the temporary user session.",
      consentTitle: "User permission required",
      consentText:
        "Admins should only access a user account after the user shares the permission code. This action should be logged by the system.",
      securityTitle: "Security note",
      securityText:
        "The code should be temporary, single-use, and verified only by the backend.",
      activityTitle: "Recent access activity",
      noActivity: "No recent access activity yet.",
    };
  }, [isRtl]);

  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [userResults, setUserResults] = useState([]);
  const [userSearchStatus, setUserSearchStatus] = useState("idle");
  const [isUserSearchOpen, setIsUserSearchOpen] = useState(false);
  const userSearchCacheRef = useRef(new Map());

  const [generateStatus, setGenerateStatus] = useState("idle");
  const [accessStatus, setAccessStatus] = useState("idle");
  const [accessRequest, setAccessRequest] = useState(null);

  const [generateError, setGenerateError] = useState("");
  const [accessError, setAccessError] = useState("");

  const hasGeneratedCode = generateStatus === "success";
  const isCodeComplete = code.length === 6;
  const deliverySummary = getDeliverySummary(accessRequest);
  const emailSearchTerm = email.trim();
  const canShowUserSearch =
    isUserSearchOpen && emailSearchTerm.length >= 1 && !isValidEmail(emailSearchTerm);

  useEffect(() => {
    const query = emailSearchTerm.toLowerCase();

    if (query.length < 1 || isValidEmail(query)) {
      const resetTimer = window.setTimeout(() => {
        setUserResults([]);
        setUserSearchStatus("idle");
      }, 0);
      return () => window.clearTimeout(resetTimer);
    }

    const cached = userSearchCacheRef.current.get(query);
    const now = Date.now();

    if (cached && now - cached.loadedAt < USER_SEARCH_CACHE_TTL_MS) {
      const cacheTimer = window.setTimeout(() => {
        setUserResults(cached.users);
        setUserSearchStatus("success");
      }, 0);
      return () => window.clearTimeout(cacheTimer);
    }

    let cancelled = false;
    const controller = new AbortController();

    const loadingTimer = window.setTimeout(() => {
      if (!cancelled) setUserSearchStatus("loading");
    }, 0);

    const timer = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          page: "1",
          page_size: "6",
          search: query,
        });

        const response = await apiFetch(getApiUrl(`/admin/users?${params.toString()}`), {
          cache: "no-store",
          signal: controller.signal,
        });

        const data = await readApiResponse(response);

        if (!response.ok) {
          throw new Error(readApiError(data, "Could not search users"));
        }

        if (!cancelled) {
          const nextUsers = Array.isArray(data.users)
            ? data.users.filter(isRegularUserAccount)
            : [];

          userSearchCacheRef.current.set(query, {
            users: nextUsers,
            loadedAt: Date.now(),
          });

          setUserResults(nextUsers);
          setUserSearchStatus("success");
        }
      } catch (error) {
        if (!cancelled && error.name !== "AbortError") {
          setUserResults([]);
          setUserSearchStatus("error");
        }
      }
    }, 220);

    return () => {
      cancelled = true;
      window.clearTimeout(loadingTimer);
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [emailSearchTerm]);

  const handleEmailChange = (event) => {
    setEmail(event.target.value);
    setIsUserSearchOpen(true);
    setGenerateError("");
    setGenerateStatus("idle");
    setAccessRequest(null);
    setAccessStatus("idle");
    setAccessError("");
  };

  const selectUserEmail = (user) => {
    const selectedEmail = String(user?.email || "").trim().toLowerCase();

    if (!selectedEmail) return;

    setEmail(selectedEmail);
    setIsUserSearchOpen(false);
    setGenerateError("");
    setGenerateStatus("idle");
    setAccessRequest(null);
    setAccessStatus("idle");
    setAccessError("");
  };

  const handleCodeChange = (event) => {
    setCode(normalizeAccessCode(event.target.value));
    setAccessError("");
    setAccessStatus("idle");
  };

  const handleGenerateCode = async (event) => {
    event.preventDefault();

    const safeEmail = email.trim().toLowerCase();

    if (!isValidEmail(safeEmail)) {
      setGenerateError(copy.invalidEmail);
      return;
    }

    setGenerateStatus("loading");
    setGenerateError("");
    setAccessError("");
    setAccessRequest(null);
    setCode("");

    try {
      const response = await apiFetch(getApiUrl("/admin/account-access/generate"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: safeEmail,
        }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(
          readAccountAccessError(
            response,
            data,
            "Could not generate permission code"
          )
        );
      }

      setGenerateStatus("success");
      setAccessRequest(data || null);
    } catch (error) {
      setGenerateStatus("error");
      setAccessRequest(null);
      setGenerateError(error.message || copy.invalidEmail);
    }
  };

  const handleAccessAccount = async (event) => {
    event.preventDefault();

    const safeEmail = email.trim().toLowerCase();

    if (!isValidEmail(safeEmail) || !hasGeneratedCode) {
      setAccessError(copy.missingEmailFirst);
      return;
    }

    if (!isCodeComplete) {
      setAccessError(copy.invalidCode);
      return;
    }

    setAccessStatus("loading");
    setAccessError("");

    try {
      const response = await apiFetch(getApiUrl("/admin/account-access/verify"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: safeEmail,
          code,
        }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(
          readAccountAccessError(
            response,
            data,
            "Invalid or expired permission code"
          )
        );
      }

      setAccessStatus("success");
      window.location.assign(data?.redirect_to || "/dashboard");
    } catch (error) {
      setAccessStatus("error");
      setAccessError(error.message || copy.invalidCode);
    }
  };

  return (
    <section
      className="admin-account-access-page dashboard-page"
      dir={isRtl ? "rtl" : "ltr"}
      data-language={isRtl ? "ar" : "en"}
      data-theme={themeMode}
    >
      <section className="admin-access-hero">
        <div>
          <span className="admin-access-eyebrow">
            <ShieldCheck size={15} aria-hidden="true" />
            {copy.eyebrow}
          </span>

          <h1>{copy.title}</h1>
          <p>{copy.subtitle}</p>
        </div>

        <div className="admin-access-hero-icon" aria-hidden="true">
          <LockKeyhole size={34} />
        </div>
      </section>

      <section className="admin-access-grid">
        <div className="admin-access-main-stack">
          <article className="dashboard-panel admin-access-form-card">
            <div className="dashboard-panel-header">
              <div>
                <h2>{copy.emailTitle}</h2>
                <p>{copy.emailLabel}</p>
              </div>

              <div className="panel-icon">
                <Mail size={22} aria-hidden="true" />
              </div>
            </div>

            <form className="admin-access-form" onSubmit={handleGenerateCode}>
              <label htmlFor="account-access-email">{copy.emailLabel}</label>

              <div className="admin-access-user-search">
                <Search
                  className="admin-access-user-search-icon"
                  size={18}
                  aria-hidden="true"
                />

                <input
                  id="account-access-email"
                  className="admin-access-email-input"
                  type="search"
                  autoComplete="off"
                  placeholder={copy.emailPlaceholder}
                  value={email}
                  onChange={handleEmailChange}
                  onFocus={() => setIsUserSearchOpen(true)}
                  onBlur={() => {
                    window.setTimeout(() => setIsUserSearchOpen(false), 140);
                  }}
                  aria-invalid={generateError ? "true" : "false"}
                  aria-expanded={canShowUserSearch ? "true" : "false"}
                  aria-controls="account-access-user-results"
                />

                {canShowUserSearch && (
                  <div
                    id="account-access-user-results"
                    className="admin-access-user-results"
                    role="listbox"
                    aria-label="Select user"
                  >
                    {userSearchStatus === "loading" && (
                      <div className="admin-access-user-result is-muted">
                        <Loader2 size={15} className="admin-access-spinner" />
                        <span>Searching users...</span>
                      </div>
                    )}

                    {userSearchStatus !== "loading" &&
                      userResults.map((result) => {
                        const resultName =
                          result.name ||
                          [result.first_name, result.last_name]
                            .filter(Boolean)
                            .join(" ") ||
                          result.email;

                        return (
                          <button
                            type="button"
                            key={result.id || result.email}
                            className="admin-access-user-result"
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={() => selectUserEmail(result)}
                            role="option"
                            aria-selected="false"
                          >
                            <UserRoundCheck size={16} aria-hidden="true" />
                            <span>
                              <strong>{resultName}</strong>
                              <small>{result.email}</small>
                            </span>
                          </button>
                        );
                      })}

                    {userSearchStatus === "success" && userResults.length === 0 && (
                      <div className="admin-access-user-result is-muted">
                        <span>No users found.</span>
                      </div>
                    )}

                    {userSearchStatus === "error" && (
                      <div className="admin-access-user-result is-muted">
                        <span>Could not search users.</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {generateError && (
                <p className="admin-access-error">
                  <AlertTriangle size={15} aria-hidden="true" />
                  {generateError}
                </p>
              )}

              {generateStatus === "success" && (
                <div className="admin-access-request-summary">
                  <div className="admin-access-summary-header">
                    <BadgeCheck size={18} aria-hidden="true" />
                    <div>
                      <strong>{deliverySummary.title}</strong>
                      <span>{deliverySummary.detail}</span>
                    </div>
                  </div>

                  <div className="admin-access-summary-grid">
                    <div className="admin-access-summary-item">
                      <UserRoundCheck size={16} aria-hidden="true" />
                      <div>
                        <span>User</span>
                        <strong>
                          {accessRequest?.target_user?.email || email}
                        </strong>
                      </div>
                    </div>

                    <div className="admin-access-summary-item">
                      <Mail size={16} aria-hidden="true" />
                      <div>
                        <span>Delivery</span>
                        <strong>{deliverySummary.deliveryLabel}</strong>
                      </div>
                    </div>

                    <div className="admin-access-summary-item">
                      <Clock3 size={16} aria-hidden="true" />
                      <div>
                        <span>Expires</span>
                        <strong>
                          {formatAccessExpiry(accessRequest?.expires_at)}
                        </strong>
                      </div>
                    </div>
                  </div>

                  <div className="admin-access-next-step">
                    <span>Next</span>
                    <strong>Enter the 6-character code below to open a temporary session.</strong>
                  </div>
                </div>
              )}

              <button
                type="submit"
                className="admin-access-submit"
                disabled={generateStatus === "loading"}
              >
                {generateStatus === "loading" ? (
                  <>
                    <Loader2 size={17} className="admin-access-spinner" />
                    {copy.generating}
                  </>
                ) : (
                  <>
                    {copy.generateCode}
                    <ArrowRight size={17} aria-hidden="true" />
                  </>
                )}
              </button>
            </form>
          </article>

          <article className="dashboard-panel admin-access-form-card">
            <div className="dashboard-panel-header">
              <div>
                <h2>{copy.codeTitle}</h2>
                <p>{copy.codeHelper}</p>
              </div>

              <div className="panel-icon">
                <KeyRound size={22} aria-hidden="true" />
              </div>
            </div>

            <form className="admin-access-form" onSubmit={handleAccessAccount}>
              <label htmlFor="permission-code">{copy.codeLabel}</label>

              <input
                id="permission-code"
                className="admin-access-code-input"
                type="text"
                inputMode="text"
                autoComplete="one-time-code"
                placeholder={copy.codePlaceholder}
                value={code}
                onChange={handleCodeChange}
                maxLength={6}
                disabled={!hasGeneratedCode}
                aria-invalid={accessError ? "true" : "false"}
              />

              <div className="admin-access-code-progress" aria-hidden="true">
                {Array.from({ length: 6 }).map((_, index) => (
                  <span
                    key={index}
                    className={index < code.length ? "is-filled" : ""}
                  />
                ))}
              </div>

              {accessError && (
                <p className="admin-access-error">
                  <AlertTriangle size={15} aria-hidden="true" />
                  {accessError}
                </p>
              )}

              {accessStatus === "success" && (
                <p className="admin-access-success">
                  <BadgeCheck size={15} aria-hidden="true" />
                  {copy.accessReady}
                </p>
              )}

              <button
                type="submit"
                className="admin-access-submit"
                disabled={accessStatus === "loading" || !hasGeneratedCode}
              >
                {accessStatus === "loading" ? (
                  <>
                    <Loader2 size={17} className="admin-access-spinner" />
                    {copy.accessing}
                  </>
                ) : (
                  <>
                    {copy.accessAccount}
                    <ArrowRight size={17} aria-hidden="true" />
                  </>
                )}
              </button>
            </form>
          </article>
        </div>

        <aside className="admin-access-side">
          <article className="dashboard-panel admin-access-info-card">
            <div className="admin-access-info-row">
              <span>
                <UserRoundCheck size={21} aria-hidden="true" />
              </span>

              <div>
                <h2>{copy.consentTitle}</h2>
                <p>{copy.consentText}</p>
              </div>
            </div>
          </article>

          <article className="dashboard-panel admin-access-info-card">
            <div className="admin-access-info-row">
              <span>
                <ShieldCheck size={21} aria-hidden="true" />
              </span>

              <div>
                <h2>{copy.securityTitle}</h2>
                <p>{copy.securityText}</p>
              </div>
            </div>
          </article>

          <article className="dashboard-panel admin-access-activity-card">
            <h2>{copy.activityTitle}</h2>
            <p>{copy.noActivity}</p>

            {currentUser?.email && (
              <small className="admin-access-current-admin">
                Admin: {currentUser.email}
              </small>
            )}
          </article>
        </aside>
      </section>
    </section>
  );
}
