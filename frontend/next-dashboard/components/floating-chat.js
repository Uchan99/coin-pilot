"use client";
import { useState } from "react";

/*
 * 플로팅 AI 채팅 버튼 — 전 페이지 우하단 고정
 * 클릭 시 채팅 패널이 슬라이드 업으로 열린다.
 * 실제 AI 응답은 Phase 3에서 백엔드 연동 예정, 현재는 UI 프레임만 구현.
 */

export default function FloatingChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "안녕하세요. CoinPilot AI 트레이딩 비서입니다. 시장/전략/리스크 질문을 입력해주세요.",
    },
  ]);
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;
    const userMsg = { role: "user", content: input.trim() };
    setMessages((prev) => [
      ...prev,
      userMsg,
      {
        role: "assistant",
        content: "AI 응답 연동은 Phase 3에서 구현됩니다. 현재는 UI 프레임입니다.",
      },
    ]);
    setInput("");
  };

  return (
    <>
      {/* 채팅 패널 */}
      {isOpen && (
        <div className="fixed bottom-24 right-8 w-[380px] h-[500px] bg-surface-high border border-outline-variant/20 rounded-xl shadow-2xl z-50 flex flex-col overflow-hidden">
          {/* 헤더 */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant/10 bg-surface-container">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-lg">
                smart_toy
              </span>
              <span className="text-sm font-semibold text-on-surface">
                AI Trading Assistant
              </span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-on-surface-variant hover:text-on-surface"
            >
              <span className="material-symbols-outlined text-lg">close</span>
            </button>
          </div>

          {/* 메시지 영역 */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[80%] px-3 py-2 rounded-lg text-sm ${
                    msg.role === "user"
                      ? "bg-primary text-on-primary"
                      : "bg-surface-container text-on-surface"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
          </div>

          {/* 입력 영역 */}
          <div className="px-4 py-3 border-t border-outline-variant/10 bg-surface-container">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="질문을 입력하세요..."
                className="flex-1 bg-surface-low text-on-surface text-sm rounded-lg px-3 py-2 border border-outline-variant/20 focus:outline-none focus:border-primary/40 placeholder:text-on-surface-variant/50"
              />
              <button
                onClick={handleSend}
                className="px-3 py-2 bg-primary text-on-primary rounded-lg text-sm font-medium hover:bg-primary-container transition-colors"
              >
                <span className="material-symbols-outlined text-lg">send</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 플로팅 버튼 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-8 right-8 w-14 h-14 bg-primary text-on-primary rounded-full shadow-2xl shadow-primary/40 flex items-center justify-center group active:scale-90 transition-transform z-50"
      >
        <span className="material-symbols-outlined text-3xl">
          {isOpen ? "close" : "smart_toy"}
        </span>
        {!isOpen && (
          <div className="absolute right-16 px-4 py-2 bg-surface-highest border border-outline-variant/20 rounded-lg text-sm text-on-surface whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none shadow-xl">
            트레이딩 도움이 필요하신가요?
          </div>
        )}
      </button>
    </>
  );
}
