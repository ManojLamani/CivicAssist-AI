export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <div className="auth-grid">
    <aside className="auth-intro">
      <p className="eyebrow">BENGALURU · KARNATAKA</p>
      <h2>A better city<br /> starts with us.</h2>
      <p>A place for citizens to connect with the issues that shape their neighbourhoods.</p>
      <p className="independent">Independent civic technology.<br />Not an official government portal.</p>
    </aside>
    {children}
  </div>;
}
