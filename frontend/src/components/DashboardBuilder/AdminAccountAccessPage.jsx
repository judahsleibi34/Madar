import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  KeyRound,
  Loader2,
  LockKeyhole,
  Mail,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";

function normalizeAccessCode(value) {
  return value.replace(/\D/g, "").slice(0, 6);
}

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
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
        "Enter the user email to generate a permission code. After the user receives the code and sends it back to you, enter the 6-digit code to access their account temporarily and securely.",
      emailTitle: "Generate permission code",
      emailLabel: "User email",
      emailPlaceholder: "user@example.com",
      generateCode: "Generate code",
      generating: "Generating...",
      codeSent:
        "Permission code sent to the user. Ask the user to send the code back to continue.",
      codeTitle: "Enter permission code",
      codeLabel: "Permission code",
      codePlaceholder: "000000",
      codeHelper: "The code must be exactly 6 digits.",
      accessAccount: "Access account",
      accessing: "Accessing...",
      invalidEmail: "Enter a valid email address.",
      invalidCode: "Enter a valid 6-digit code.",
      missingEmailFirst: "Generate the code first before entering permission code.",
      accessReady:
        "Code verified. Later, connect this step to redirect the admin into the user session.",
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

  const [generateStatus, setGenerateStatus] = useState("idle");
  const [accessStatus, setAccessStatus] = useState("idle");

  const [generateError, setGenerateError] = useState("");
  const [accessError, setAccessError] = useState("");

  const hasGeneratedCode = generateStatus === "success";
  const isCodeComplete = code.length === 6;

  const handleEmailChange = (event) => {
    setEmail(event.target.value);
    setGenerateError("");
    setGenerateStatus("idle");
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
    setCode("");

    try {
      /*
        Backend endpoint for later:

        const response = await fetch("/api/admin/account-access/generate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({
            email: safeEmail,
          }),
        });

        if (!response.ok) {
          throw new Error("Could not generate permission code");
        }

        const data = await response.json();
      */

      await new Promise((resolve) => setTimeout(resolve, 700));

      setGenerateStatus("success");
    } catch (error) {
      setGenerateStatus("error");
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
      /*
        Backend endpoint for later:

        const response = await fetch("/api/admin/account-access/verify", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({
            email: safeEmail,
            code,
          }),
        });

        if (!response.ok) {
          throw new Error("Invalid or expired permission code");
        }

        const data = await response.json();

        Redirect example:
        navigate(data.redirectTo || "/dashboard");
      */

      await new Promise((resolve) => setTimeout(resolve, 700));

      setAccessStatus("success");
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

              <input
                id="account-access-email"
                className="admin-access-email-input"
                type="email"
                autoComplete="email"
                placeholder={copy.emailPlaceholder}
                value={email}
                onChange={handleEmailChange}
                aria-invalid={generateError ? "true" : "false"}
              />

              {generateError && (
                <p className="admin-access-error">
                  <AlertTriangle size={15} aria-hidden="true" />
                  {generateError}
                </p>
              )}

              {generateStatus === "success" && (
                <p className="admin-access-success">
                  <BadgeCheck size={15} aria-hidden="true" />
                  {copy.codeSent}
                </p>
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
                inputMode="numeric"
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