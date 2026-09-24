import AuthToast from "../AuthPages/AuthToast";

export default function EcommerceToast({ type = "error", ...props }) {
  return (
    <AuthToast
      {...props}
      type={type}
      className="ecommerce-toast"
      duration={type === "error" ? 6500 : 4400}
    />
  );
}
