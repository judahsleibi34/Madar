export default function SectionBlock({ as: Component = "section", className, children, ...props }) {
  return (
    <Component className={className} {...props}>
      {children}
    </Component>
  );
}
