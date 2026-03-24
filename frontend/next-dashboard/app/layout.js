import "./globals.css";
import Sidebar from "@/components/sidebar";
import Topbar from "@/components/topbar";
import FloatingChat from "@/components/floating-chat";

export const metadata = {
  title: "CoinPilot v3.0 Dashboard",
  description: "AI-Powered Crypto Trading System Dashboard",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko" className="dark">
      <head>
        {/* Inter 폰트 */}
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        {/* Material Symbols 아이콘 */}
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-surface text-on-surface font-sans">
        <Sidebar />
        <main className="ml-[240px] min-h-screen flex flex-col">
          <Topbar />
          <div className="flex-1 p-8 max-w-7xl mx-auto w-full">
            {children}
          </div>
        </main>
        <FloatingChat />
      </body>
    </html>
  );
}
