export default function SplitText({
  children,
  className = "",
  delay = 0.035,
  duration = 0.42,
  as: Component = "span",
}) {
  const text = String(children || "");
  const characters = Array.from(text);

  return (
    <Component
      className={["split-text", className].filter(Boolean).join(" ")}
      aria-label={text}
      style={{
        "--split-text-delay": `${delay}s`,
        "--split-text-duration": `${duration}s`,
      }}
    >
      {characters.map((character, index) => (
        <span
          aria-hidden="true"
          className="split-text-character"
          key={`${character}-${index}`}
          style={{ "--split-text-index": index }}
        >
          {character === " " ? "\u00a0" : character}
        </span>
      ))}
    </Component>
  );
}
