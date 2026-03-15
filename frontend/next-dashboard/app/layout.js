import "./globals.css";

export const metadata = {
  title: "CoinPilot Next Dashboard",
  description: "Read-only Next.js MVP for CoinPilot overview and system health"
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>
        <div className="page-shell">
          <header className="topbar">
            <div>
              <p className="topbar-kicker">CoinPilot / Phase 1</p>
              <h1>Next Dashboard Read-Only MVP</h1>
            </div>
            <nav className="topbar-nav">
              <a href="/">Overview</a>
              <a href="/system">System</a>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
