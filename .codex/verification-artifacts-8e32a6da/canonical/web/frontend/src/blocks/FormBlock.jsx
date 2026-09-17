export default function FormBlock({ className, children, ...props }) {
  return (
    <form className={className} {...props}>
      {children}
    </form>
  );
}
