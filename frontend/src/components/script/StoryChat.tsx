import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, Sparkles, Copy, Check, Mic, MicOff } from 'lucide-react';
import { chatStory } from '../../services/api';
import type { ChatMessage } from '../../services/api';

const T = {
  bg: '#0a0a0a', card: '#111111', gold: '#D4A843', goldLight: '#F0D78C',
  goldGrad: 'linear-gradient(135deg, #FFF1B8, #F0D78C, #D4A843, #8B6914)',
  silverLight: '#E8E8E8', dim: '#888', dimmer: '#555',
  border: 'rgba(212,168,67,0.1)',
};

interface StoryChatProps {
  onScriptReady: (script: string) => void;
}

interface DisplayMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  script?: string | null;
}

export function StoryChat({ onScriptReady }: StoryChatProps) {
  const [messages, setMessages] = useState<DisplayMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hey! I'm your AI writing partner. Tell me your story idea — even a vague one works. I'll help you shape it into a full script ready for comics, manga, or storyboards. 🎬\n\nWhat's your story about?",
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);

  // Web Speech API support
  const speechSupported = typeof window !== 'undefined' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

  const toggleListening = useCallback(() => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    let finalTranscript = '';

    recognition.onresult = (event: any) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript + ' ';
        } else {
          interim = transcript;
        }
      }
      setInput(finalTranscript + interim);
    };

    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, [isListening]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userMsg: DisplayMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      // Build history (exclude welcome message)
      const history: ChatMessage[] = messages
        .filter((m) => m.id !== 'welcome')
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await chatStory(history, text);

      const assistantMsg: DisplayMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: res.reply,
        script: res.script,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: 'Something went wrong. Try again?',
        },
      ]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }, [input, isLoading, messages]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const useScript = (script: string) => {
    onScriptReady(script);
  };

  const copyScript = (id: string, script: string) => {
    navigator.clipboard.writeText(script);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      height: 420, borderRadius: 12,
      background: T.card, border: `1px solid ${T.border}`,
      overflow: 'hidden',
    }}>
      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '16px 16px 8px',
        display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        {messages.map((msg) => (
          <div key={msg.id} style={{
            display: 'flex',
            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
          }}>
            <div style={{
              maxWidth: '85%', padding: '10px 14px', borderRadius: 12,
              background: msg.role === 'user'
                ? 'rgba(212,168,67,0.12)'
                : 'rgba(255,255,255,0.04)',
              border: msg.role === 'user'
                ? '1px solid rgba(212,168,67,0.2)'
                : '1px solid rgba(255,255,255,0.06)',
            }}>
              <p style={{
                fontSize: 13, lineHeight: 1.6, margin: 0,
                color: msg.role === 'user' ? T.goldLight : T.silverLight,
                whiteSpace: 'pre-wrap',
              }}>
                {msg.content}
              </p>

              {/* Script block with action buttons */}
              {msg.script && (
                <div style={{
                  marginTop: 10, padding: 12, borderRadius: 8,
                  background: 'rgba(212,168,67,0.06)',
                  border: '1px solid rgba(212,168,67,0.15)',
                }}>
                  <pre style={{
                    fontSize: 11, lineHeight: 1.5, color: T.silverLight,
                    whiteSpace: 'pre-wrap', fontFamily: 'monospace',
                    margin: 0, maxHeight: 200, overflowY: 'auto',
                  }}>
                    {msg.script}
                  </pre>
                  <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                    <button
                      onClick={() => useScript(msg.script!)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '6px 14px', borderRadius: 8,
                        background: T.goldGrad, border: 'none',
                        color: T.bg, fontSize: 11, fontWeight: 700,
                        cursor: 'pointer',
                        boxShadow: '0 2px 8px rgba(212,168,67,0.2)',
                      }}
                    >
                      <Sparkles size={12} /> Use This Script
                    </button>
                    <button
                      onClick={() => copyScript(msg.id, msg.script!)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '6px 14px', borderRadius: 8,
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.08)',
                        color: T.dim, fontSize: 11, fontWeight: 500,
                        cursor: 'pointer',
                      }}
                    >
                      {copiedId === msg.id ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div style={{
              padding: '10px 14px', borderRadius: 12,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.06)',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <Loader2 size={14} color={T.gold} style={{ animation: 'spin 1s linear infinite' }} />
              <span style={{ fontSize: 12, color: T.dim }}>Thinking...</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '10px 12px', borderTop: `1px solid ${T.border}`,
        display: 'flex', gap: 8, alignItems: 'flex-end',
      }}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe your story idea..."
          rows={1}
          style={{
            flex: 1, padding: '10px 14px', borderRadius: 10,
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
            color: T.silverLight, fontSize: 13, fontFamily: 'inherit',
            resize: 'none', outline: 'none',
            maxHeight: 100, lineHeight: 1.5,
          }}
          onInput={(e) => {
            const t = e.currentTarget;
            t.style.height = 'auto';
            t.style.height = Math.min(t.scrollHeight, 100) + 'px';
          }}
        />
        {speechSupported && (
          <button
            onClick={toggleListening}
            title={isListening ? 'Stop listening' : 'Voice input'}
            style={{
              width: 38, height: 38, borderRadius: 10,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: isListening ? 'rgba(220,50,50,0.2)' : 'rgba(255,255,255,0.04)',
              border: isListening ? '1px solid rgba(220,50,50,0.4)' : '1px solid rgba(255,255,255,0.08)',
              cursor: 'pointer',
              transition: 'all 0.2s', flexShrink: 0,
              animation: isListening ? 'pulse 1.5s ease-in-out infinite' : 'none',
            }}
          >
            {isListening ? <MicOff size={16} color="#dc3232" /> : <Mic size={16} color={T.dim} />}
          </button>
        )}
        <button
          onClick={sendMessage}
          disabled={!input.trim() || isLoading}
          style={{
            width: 38, height: 38, borderRadius: 10,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: input.trim() && !isLoading ? T.goldGrad : 'rgba(255,255,255,0.04)',
            border: 'none',
            cursor: input.trim() && !isLoading ? 'pointer' : 'default',
            transition: 'all 0.2s', flexShrink: 0,
          }}
        >
          <Send size={16} color={input.trim() && !isLoading ? T.bg : T.dimmer} />
        </button>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
      `}</style>
    </div>
  );
}
