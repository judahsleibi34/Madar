import { useEffect, useRef } from "react";
import { animate, useInView, useMotionValue, useTransform, motion } from "framer-motion";

const numberPattern = /-?[\d,.]+/;

export default function CountUpText({ value, duration = 2 }) {
  const text = String(value ?? "0");
  const match = text.match(numberPattern);
  const target = Number(String(match?.[0] || "0").replace(/,/g, ""));
  const decimals = match?.[0]?.includes(".") ? match[0].split(".")[1].length : 0;
  const prefix = match ? text.slice(0, match.index) : "";
  const suffix = match ? text.slice((match.index || 0) + match[0].length) : text;
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-10%" });
  const count = useMotionValue(0);
  const display = useTransform(count, (latest) =>
    `${prefix}${latest.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })}`
  );

  useEffect(() => {
    if (!isInView || !Number.isFinite(target)) return undefined;
    const controls = animate(count, target, { duration, ease: "easeOut" });
    return () => controls.stop();
  }, [count, duration, isInView, target]);

  if (!match || !Number.isFinite(target)) return <span ref={ref}>{text}</span>;

  return (
    <span ref={ref} className="count-up-number">
      <motion.span>{display}</motion.span>
      {suffix && <span className="count-up-suffix">{suffix}</span>}
    </span>
  );
}
