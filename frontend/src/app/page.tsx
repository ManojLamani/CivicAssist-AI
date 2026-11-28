import Link from "next/link";

export default function Home() {
  return <section className="home-panel">
    <p className="eyebrow">BENGALURU · CIVICASSIST</p>
    <h1>CivicAssist AI</h1>
    <p>Your citizen account is the first step. Complaint reporting and civic services are still in development.</p>
    <div className="home-actions"><Link className="button" href="/register">Create account</Link><Link href="/login">Sign in</Link></div>
    <p className="hint">An independent platform, without an official government integration.</p>
  </section>;
}
