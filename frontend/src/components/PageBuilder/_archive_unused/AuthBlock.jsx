import { useState } from "react";
import "./AuthBlock.css";

const defaultCopy = {
  login: {
    title: "Log in",
    subtitle: "Access your account and continue to your workspace.",
    buttonText: "Log in",
    switchText: "Don't have an account?",
    switchActionText: "Create account",
  },
  register: {
    title: "Register",
    subtitle: "Create an account to save requests, reservations, and private activity.",
    buttonText: "Create Account",
    switchText: "Already registered?",
    switchActionText: "Log in",
  },
};

const initialValues = {
  firstName: "",
  lastName: "",
  email: "",
  password: "",
  confirmPassword: "",
};

export default function AuthBlock({
  mode = "login",
  title,
  subtitle,
  buttonText,
  switchText,
  switchActionText,
  disabled = false,
  onLogin,
  onRegister,
}) {
  const [activeMode, setActiveMode] = useState(mode === "register" ? "register" : "login");
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const customCopyApplies = activeMode === (mode === "register" ? "register" : "login");
  const copy = {
    ...defaultCopy[activeMode],
    ...(customCopyApplies
      ? {
          title: title || defaultCopy[activeMode].title,
          subtitle: subtitle || defaultCopy[activeMode].subtitle,
          buttonText: buttonText || defaultCopy[activeMode].buttonText,
          switchText: switchText || defaultCopy[activeMode].switchText,
          switchActionText: switchActionText || defaultCopy[activeMode].switchActionText,
        }
      : {}),
  };
  const isRegister = activeMode === "register";

  const updateValue = (key, value) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const validate = () => {
    const nextErrors = {};

    if (isRegister && !values.firstName.trim()) nextErrors.firstName = "Required";
    if (isRegister && !values.lastName.trim()) nextErrors.lastName = "Required";
    if (!values.email.trim()) nextErrors.email = "Required";
    if (!values.password.trim()) nextErrors.password = "Required";
    if (isRegister && values.password !== values.confirmPassword) {
      nextErrors.confirmPassword = "Passwords do not match";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const submit = (event) => {
    event.preventDefault();
    if (!validate()) return;

    if (isRegister) {
      onRegister?.(values);
      setActiveMode("login");
    } else {
      onLogin?.(values);
    }

    setValues(initialValues);
  };

  const switchMode = () => {
    setErrors({});
    setActiveMode((current) => (current === "login" ? "register" : "login"));
  };

  return (
    <form className={`auth-block auth-block-${activeMode}`} onSubmit={submit}>
      <div className="auth-block-heading">
        <span>{isRegister ? "Registration" : "Login"}</span>
        <h3>{copy.title}</h3>
        <p>{copy.subtitle}</p>
      </div>

      <div className="auth-block-grid">
        {isRegister && (
          <>
            <label className={errors.firstName ? "has-error" : ""}>
              First Name
              <input
                value={values.firstName}
                disabled={disabled}
                placeholder="First Name"
                onChange={(event) => updateValue("firstName", event.target.value)}
              />
              {errors.firstName && <strong>{errors.firstName}</strong>}
            </label>

            <label className={errors.lastName ? "has-error" : ""}>
              Last Name
              <input
                value={values.lastName}
                disabled={disabled}
                placeholder="Last Name"
                onChange={(event) => updateValue("lastName", event.target.value)}
              />
              {errors.lastName && <strong>{errors.lastName}</strong>}
            </label>
          </>
        )}

        <label className={`auth-field-wide ${errors.email ? "has-error" : ""}`}>
          Email
          <input
            type="email"
            value={values.email}
            disabled={disabled}
            placeholder="Email"
            onChange={(event) => updateValue("email", event.target.value)}
          />
          {errors.email && <strong>{errors.email}</strong>}
        </label>

        <label className={`auth-field-wide ${errors.password ? "has-error" : ""}`}>
          Password
          <div className="auth-password-field">
            <input
              type={showPassword ? "text" : "password"}
              value={values.password}
              disabled={disabled}
              placeholder="Password"
              onChange={(event) => updateValue("password", event.target.value)}
            />
            <button type="button" disabled={disabled} onClick={() => setShowPassword((value) => !value)}>
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
          {errors.password && <strong>{errors.password}</strong>}
        </label>

        {isRegister && (
          <label className={`auth-field-wide ${errors.confirmPassword ? "has-error" : ""}`}>
            Confirm Password
            <div className="auth-password-field">
              <input
                type={showConfirmPassword ? "text" : "password"}
                value={values.confirmPassword}
                disabled={disabled}
                placeholder="Confirm Password"
                onChange={(event) => updateValue("confirmPassword", event.target.value)}
              />
              <button type="button" disabled={disabled} onClick={() => setShowConfirmPassword((value) => !value)}>
                {showConfirmPassword ? "Hide" : "Show"}
              </button>
            </div>
            {errors.confirmPassword && <strong>{errors.confirmPassword}</strong>}
          </label>
        )}
      </div>

      <button className="auth-submit" type="submit" disabled={disabled}>
        {copy.buttonText}
      </button>

      <p className="auth-switch">
        {copy.switchText}{" "}
        <button type="button" onClick={switchMode}>
          {copy.switchActionText}
        </button>
      </p>

      {disabled && <p className="auth-helper">Enable Preview to test this form.</p>}
    </form>
  );
}
