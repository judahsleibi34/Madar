export default function CardGridBlock({ as: Component = "section", className, items = [], renderItem, ...props }) {
  return (
    <Component className={className} {...props}>
      {items.map(renderItem)}
    </Component>
  );
}
