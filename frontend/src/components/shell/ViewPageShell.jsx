export default function ViewPageShell({ title, children }) {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-8">
      {title ? <h1 className="text-center text-2xl font-bold">{title}</h1> : null}
      {children}
    </div>
  );
}
