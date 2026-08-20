export default function FormButton({
  children,
  ariaLabel,
  className = "",
  disabled = false,
  icon: Icon,
  onClick,
  title,
  variant = "default",
}) {
  const classes = ["form-command-button", `form-command-button-${variant}`, className]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={classes}
      disabled={disabled}
      onClick={onClick}
      aria-label={ariaLabel || (typeof children === "string" ? children : title)}
      title={title}
    >
      {Icon && <Icon size={16} aria-hidden="true" />}
      {children}
    </button>
  );
}
