export default function Home() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  return <main>
    <h1>CivicAssist AI</h1>
    <p>Development setup is ready. Product features are not implemented yet.</p>
    <a href={`${apiUrl}/docs`}>Open API documentation</a>
  </main>;
}
