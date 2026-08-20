import { Link, NavLink } from "react-router-dom";

export default function SmartLink({
  to,
  children,
  className,
  activeClassName = "active",
  nav = false,
  onClick,
  ...props
}) {
  const isExternal =
    typeof to === "string" &&
    (to.startsWith("http://") || to.startsWith("https://") || to.startsWith("mailto:") || to.startsWith("tel:"));

  if (isExternal) {
    return (
      <a
        href={to}
        className={className}
        onClick={onClick}
        target="_blank"
        rel="noreferrer"
        {...props}
      >
        {children}
      </a>
    );
  }

  if (nav) {
    return (
      <NavLink
        to={to}
        className={({ isActive }) => {
          const base =
            typeof className === "function" ? className({ isActive }) : className || "";

          return isActive ? `${base} ${activeClassName}`.trim() : base;
        }}
        onClick={onClick}
        {...props}
      >
        {children}
      </NavLink>
    );
  }

  return (
    <Link to={to} className={className} onClick={onClick} {...props}>
      {children}
    </Link>
  );
}