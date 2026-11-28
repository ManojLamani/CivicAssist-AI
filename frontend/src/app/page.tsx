import Link from "next/link";

export default function Home() {
  return <section className="home-panel">
    <p className="eyebrow">BENGALURU · CIVICASSIST</p>
    <h1>CivicAssist AI</h1>
    <p>Create a citizen account to report a civic issue and view your saved complaints.</p>
    <div className="home-actions"><Link className="button" href="/register">Create account</Link><Link href="/login">Sign in</Link></div>
    <p className="hint">An independent platform, without an official government integration.</p>
  </section>;
}
