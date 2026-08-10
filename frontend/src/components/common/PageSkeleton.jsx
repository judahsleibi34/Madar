import LoadingBar from "./LoadingBar";

export default function PageSkeleton({
  label = "Loading page",
  lang = "en",
  variant = "public-page",
}) {
  return (
    <main
      className={`page-skeleton page-skeleton-${variant}`}
      dir={lang === "ar" ? "rtl" : "ltr"}
      aria-busy="true"
      aria-label={label}
    >
      <LoadingBar label={label} />
    </main>
  );
}
