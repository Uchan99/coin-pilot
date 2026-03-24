"use client";
import { useState, useRef, useEffect } from "react";
import { askChatbot } from "@/lib/bot-api";

/*
 * AI Chatbot 풀페이지 — Stitch 디자인
 * Phase 3: /api/mobile/ask 실 AI 응답 연동
 * 퀵 제안 카드 4개 + 메시지 버블 + 입력 영역
 */

const QUICK_SUGGESTIONS = [
  { icon: "account_balance_wallet", text: "현재 잔고와 포지션 상태 알려줘", color: "primary" },
  { icon: "show_chart", text: "현재 비트코인 시장 어떻게 봐?", color: "tertiary" },
  { icon: "psychology", text: "최근 매매 기준으로 장단점 분석해줘", color: "secondary" },
  { icon: "security", text: "지금 레짐에서 주의할 위험이 뭐야?", color: "error" },
];

const COLOR_CLS = {
  primary: "bg-primary/10 text-primary",
  tertiary: "bg-tertiary/10 text-tertiary",
  secondary: "bg-secondary/10 text-secondary",
  error: "bg-error/10 text-error",
};

export default function ChatbotPage() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "안녕하세요. CoinPilot AI 트레이딩 비서입니다. 시장/전략/리스크 질문을 입력해주세요.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `web-${Date.now()}`);
  const messagesEndRef = useRef(null);

  // 메시지 추가 시 자동 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text) => {
    const msg = text || input.trim();
    if (!msg || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setInput("");
    setLoading(true);

    // AI 응답 요청
    const answer = await askChatbot(msg, sessionId);

    setMessages((prev) => [...prev, { role: "assistant", content: answer }]);
    setLoading(false);
  };

  const handleClear = () => {
    setMessages([
      { role: "assistant", content: "대화가 초기화되었습니다. 새로운 질문을 입력해주세요." },
    ]);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* 헤더 */}
      <div className="text-center mb-6">
        <div className="w-16 h-16 mx-auto mb-4 bg-primary/10 rounded-2xl flex items-center justify-center">
          <span className="material-symbols-outlined text-primary text-3xl">smart_toy</span>
        </div>
        <h2 className="text-2xl font-bold">AI Trading Assistant</h2>
        <p className="text-sm text-on-surface-variant mt-1">
          실시간 데이터 기반의 지능형 트레이딩 분석 비서입니다.
        </p>
        <button
          onClick={handleClear}
          className="mt-3 px-4 py-1.5 bg-surface-container text-on-surface-variant text-xs rounded-lg border border-outline-variant/20 hover:bg-surface-high transition-colors"
        >
          Clear Conversation
        </button>
      </div>

      {/* 퀵 제안 카드 */}
      {messages.length <= 1 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {QUICK_SUGGESTIONS.map(({ icon, text, color }) => (
            <button
              key={text}
              onClick={() => handleSend(text)}
              disabled={loading}
              className="bg-surface-container p-4 rounded-xl border border-outline-variant/10 hover:bg-surface-high transition-colors text-left group disabled:opacity-50"
            >
              <span className={`material-symbols-outlined text-lg mb-2 ${COLOR_CLS[color]?.split(" ")[1] || "text-primary"}`}>
                {icon}
              </span>
              <p className="text-xs text-on-surface-variant leading-relaxed">{text}</p>
            </button>
          ))}
        </div>
      )}

      {/* 메시지 영역 */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 px-2">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center mr-3 flex-none">
                <span className="material-symbols-outlined text-primary text-sm">smart_toy</span>
              </div>
            )}
            <div className={`max-w-[70%] px-4 py-3 rounded-xl text-sm leading-relaxed whitespace-pre-wrap ${
              msg.role === "user"
                ? "bg-primary text-on-primary rounded-br-sm"
                : "bg-surface-container text-on-surface rounded-bl-sm"
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center mr-3 flex-none">
              <span className="material-symbols-outlined text-primary text-sm animate-spin">progress_activity</span>
            </div>
            <div className="bg-surface-container text-on-surface-variant px-4 py-3 rounded-xl text-sm rounded-bl-sm">
              AI가 분석 중입니다...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 입력 영역 */}
      <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-4">
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && handleSend()}
            placeholder="질문을 입력하세요..."
            disabled={loading}
            className="flex-1 bg-surface-low text-on-surface text-sm rounded-lg px-4 py-3 border border-outline-variant/20 focus:outline-none focus:border-primary/40 placeholder:text-on-surface-variant/50 disabled:opacity-50"
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            className="px-5 py-3 bg-gradient-to-br from-primary to-primary-container text-on-primary font-semibold rounded-xl active:scale-95 transition-all disabled:opacity-50"
          >
            <span className="material-symbols-outlined">send</span>
          </button>
        </div>
      </div>
    </div>
  );
}
