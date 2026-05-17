export default function PageHeading({ title, className, style, as: Tag = "h1" }) {
  return (
    <Tag className={className} style={style}>
      {title}
    </Tag>
  );
}
