import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  KeyRound,
  Loader2,
  LockKeyhole,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";

function normalizeAccessCode(value) {
  return value.replace(/\D/g, "").slice(0, 6);
}

export default function AdminAccountAccessPage({
  lang = "en",
  themeMode = "light",
}) {
  const isRtl = lang === "ar";

  const copy = useMemo(() => {
    if (isRtl) {
      return {
        eyebrow: "وصول المسؤول",
        title: "الدخول إلى حساب مستخدم بإذن",
        subtitle:
          "أدخل رمز الإذن المكون من 6 أرقام الذي أعطاه لك المستخدم للوصول إلى حسابه بشكل مؤقت وآمن.",
        codeLabel: "رمز الإذن",
        codePlaceholder: "000000",
        helper: "يجب أن يكون الرمز مكونًا من 6 أرقام.",
        verify: "التحقق والدخول",
        verifying: "جاري التحقق...",
        consentTitle: "الوصول يتطلب موافقة المستخدم",
        consentText:
          "لا يمكن الدخول إلى حساب المستخدم إلا بعد أن يشارك رمز الإذن بنفسه. يجب تسجيل هذا الإجراء في النظام.",
        securityTitle: "ملاحظة أمنية",
        securityText:
          "لا تحفظ رمز الإذن في المتصفح. يجب التحقق منه من الخادم، ويجب أن تنتهي صلاحيته بعد مدة قصيرة.",
        invalidCode: "أدخل رمزًا صحيحًا من 6 أرقام.",
        readyText:
          "النموذج جاهز. اربطه لاحقًا مع API يتحقق من الرمز ويفتح جلسة وصول محدودة.",
        recentTitle: "آخر إجراءات الوصول",
        noActivity: "لا توجد إجراءات وصول حديثة.",
      };
    }

    return {
      eyebrow: "Admin Access",
      title: "Access a user account with permission",
      subtitle:
        "Enter the 6-digit permission code shared by the user to access their account temporarily and securely.",
      codeLabel: "Permission code",
      codePlaceholder: "000000",
      helper: "The code must be exactly 6 digits.",
      verify: "Verify and access",
      verifying: "Verifying...",
      consentTitle: "User permission required",
      consentText:
        "Admins should only access a user account after the user shares their permission code. This action should be logged by the system.",
      securityTitle: "Security note",
      securityText:
        "Do not store the permission code in the browser. The backend should verify it, expire it quickly, and return a limited admin-access session.",
      invalidCode: "Enter a valid 6-digit code.",
      readyText:
        "The form is ready. Later, connect it to an API that verifies the code and opens a limited user-account session.",
      recentTitle: "Recent access activity",
      noActivity: "No recent access activity yet.",
    };
  }, [isRtl]);

  const [code, setCode] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const isCodeComplete = code.length === 6;

  const handleCodeChange = (event) => {
    setCode(normalizeAccessCode(event.target.value));
    setError("");
    setStatus("idle");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!isCodeComplete) {
      setError(copy.invalidCode);
      return;
    }

    setStatus("loading");
    setError("");

    try {
      /*
        Backend placeholder for later:

        const response = await fetch("/api/admin/account-access/verify", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({ code }),
        });

        if (!response.ok) {
          throw new Error("Invalid or expired permission code");
        }

        const data = await response.json();

        navigate(data.redirectTo || "/dashboard");
      */

      await new Promise((resolve) => setTimeout(resolve, 700));

      setStatus("success");
    } catch (submitError) {
      setStatus("error");
      setError(submitError.message || copy.invalidCode);
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
        <article className="dashboard-panel admin-access-form-card">
          <div className="dashboard-panel-header">
            <div>
              <h2>{copy.codeLabel}</h2>
              <p>{copy.helper}</p>
            </div>

            <div className="panel-icon">
              <KeyRound size={22} aria-hidden="true" />
            </div>
          </div>

          <form className="admin-access-form" onSubmit={handleSubmit}>
            <label htmlFor="permission-code">{copy.codeLabel}</label>

            <input
              id="permission-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder={copy.codePlaceholder}
              value={code}
              onChange={handleCodeChange}
              maxLength={6}
              aria-invalid={error ? "true" : "false"}
            />

            <div className="admin-access-code-progress" aria-hidden="true">
              {Array.from({ length: 6 }).map((_, index) => (
                <span
                  key={index}
                  className={index < code.length ? "is-filled" : ""}
                />
              ))}
            </div>

            {error && (
              <p className="admin-access-error">
                <AlertTriangle size={15} aria-hidden="true" />
                {error}
              </p>
            )}

            {status === "success" && (
              <p className="admin-access-success">
                <BadgeCheck size={15} aria-hidden="true" />
                {copy.readyText}
              </p>
            )}

            <button
              type="submit"
              className="admin-access-submit"
              disabled={status === "loading"}
            >
              {status === "loading" ? (
                <>
                  <Loader2 size={17} className="admin-access-spinner" />
                  {copy.verifying}
                </>
              ) : (
                <>
                  {copy.verify}
                  <ArrowRight size={17} aria-hidden="true" />
                </>
              )}
            </button>
          </form>
        </article>

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
            <h2>{copy.recentTitle}</h2>
            <p>{copy.noActivity}</p>
          </article>
        </aside>
      </section>
    </section>
  );
}