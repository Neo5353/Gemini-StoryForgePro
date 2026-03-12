import { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Send, Sparkles, ToggleLeft, ToggleRight, ArrowLeftRight } from 'lucide-react';
import { sendEdit } from '../../services/api';
import type { EditMessage, EditRequest } from '../../types';

interface ChatEditorProps {
  projectId: string;
  targetId: string;
}

export function ChatEditor({ projectId, targetId }: ChatEditorProps) {
  const [messages, setMessages] = useState<EditMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: EditMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      before_url: null,
      after_url: null,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const req: EditRequest = { project_id: projectId, target_id: targetId, instruction: userMessage.content };
      const response = await sendEdit(req);
      setMessages((prev) => [...prev, response]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: 'Edit failed. Try a different instruction.',
          before_url: null,
          after_url: null,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full rounded-xl border border-neutral-700/50 bg-neutral-800/30 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-700/50">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-purple-400" />
          <span className="text-sm font-medium text-neutral-300">Edit Studio</span>
        </div>
        <button
          onClick={() => setCompareMode(!compareMode)}
          className="flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
        >
          {compareMode ? <ToggleRight size={16} className="text-purple-400" /> : <ToggleLeft size={16} />}
          A/B Compare
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {messages.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-neutral-600">
            <ArrowLeftRight size={24} className="mb-2 opacity-50" />
            <p className="text-sm">Send edit instructions to refine your output</p>
            <p className="text-xs mt-1">e.g. "make the lighting warmer" or "add rain"</p>
          </div>
        )}

        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex flex-col gap-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div
              className={`max-w-[85%] px-4 py-2.5 rounded-xl text-sm ${
                msg.role === 'user'
                  ? 'bg-purple-600/80 text-white'
                  : 'bg-neutral-800 text-neutral-300 border border-neutral-700/50'
              }`}
            >
              {msg.content}
            </div>

            {/* Before/After comparison */}
            {compareMode && msg.before_url && msg.after_url && (
              <div className="flex gap-2 max-w-[85%]">
                <div className="flex-1">
                  <span className="text-[10px] text-neutral-500 mb-1 block">Before</span>
                  <img src={msg.before_url} alt="Before" className="rounded-lg border border-neutral-700" />
                </div>
                <div className="flex-1">
                  <span className="text-[10px] text-neutral-500 mb-1 block">After</span>
                  <img src={msg.after_url} alt="After" className="rounded-lg border border-purple-600/50" />
                </div>
              </div>
            )}

            {!compareMode && msg.after_url && (
              <img
                src={msg.after_url}
                alt="Result"
                className="max-w-[85%] rounded-lg border border-neutral-700/50"
              />
            )}
          </motion.div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="px-4 py-2.5 rounded-xl bg-neutral-800 border border-neutral-700/50 text-neutral-400 text-sm flex items-center gap-2">
              <Sparkles size={14} className="animate-pulse text-purple-400" />
              Processing edit...
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-neutral-700/50">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Describe your edit..."
            className="flex-1 px-4 py-2.5 rounded-xl bg-neutral-800 border border-neutral-700 text-sm text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30 transition-all"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="px-4 py-2.5 rounded-xl bg-purple-600 text-white hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
