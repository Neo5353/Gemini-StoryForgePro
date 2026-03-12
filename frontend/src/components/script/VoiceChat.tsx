import { useState, useRef, useCallback, useEffect } from 'react';
import { Mic, MicOff, Phone, PhoneOff, Volume2 } from 'lucide-react';

const T = {
  bg: '#0a0a0a', card: '#111111', gold: '#D4A843', goldLight: '#F0D78C',
  goldGrad: 'linear-gradient(135deg, #FFF1B8, #F0D78C, #D4A843, #8B6914)',
  silverLight: '#E8E8E8', dim: '#888', dimmer: '#555',
  border: 'rgba(212,168,67,0.1)',
};

interface VoiceChatProps {
  onScriptReady: (script: string) => void;
}

type SessionState = 'idle' | 'connecting' | 'connected' | 'error';

export function VoiceChat({ onScriptReady }: VoiceChatProps) {
  const [state, setState] = useState<SessionState>('idle');
  const [isMuted, setIsMuted] = useState(false);
  const [transcript, setTranscript] = useState<string[]>([]);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  const getWsUrl = () => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = import.meta.env.VITE_WS_URL
      ? new URL(import.meta.env.VITE_WS_URL).host
      : window.location.host;
    return `${proto}//${host}/api/voice/live`;
  };

  const playAudioChunk = async (base64Data: string) => {
    try {
      if (!playbackCtxRef.current) {
        playbackCtxRef.current = new AudioContext({ sampleRate: 24000 });
      }
      const ctx = playbackCtxRef.current;
      const raw = atob(base64Data);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
      
      // PCM 16-bit mono → Float32
      const samples = new Float32Array(bytes.length / 2);
      const view = new DataView(bytes.buffer);
      for (let i = 0; i < samples.length; i++) {
        samples[i] = view.getInt16(i * 2, true) / 32768;
      }

      const buffer = ctx.createBuffer(1, samples.length, 24000);
      buffer.copyToChannel(samples, 0);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      source.start();
    } catch (e) {
      console.error('Audio playback error:', e);
    }
  };

  const connect = useCallback(async () => {
    setState('connecting');
    setTranscript([]);

    try {
      // Get microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      // Set up audio processing
      const audioCtx = new AudioContext({ sampleRate: 16000 });
      audioCtxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      // Connect WebSocket
      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        setState('connected');
        setTranscript(prev => [...prev, '🎙️ Connected — start speaking!']);

        // Start sending audio
        source.connect(processor);
        processor.connect(audioCtx.destination);

        processor.onaudioprocess = (e) => {
          if (isMuted || ws.readyState !== WebSocket.OPEN) return;
          const input = e.inputBuffer.getChannelData(0);
          // Float32 → PCM 16-bit
          const pcm = new Int16Array(input.length);
          for (let i = 0; i < input.length; i++) {
            pcm[i] = Math.max(-32768, Math.min(32767, Math.round(input[i] * 32768)));
          }
          const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm.buffer)));
          ws.send(JSON.stringify({ type: 'audio', data: b64 }));
        };
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'audio') {
          setAiSpeaking(true);
          playAudioChunk(msg.data);
        } else if (msg.type === 'text') {
          setTranscript(prev => [...prev, `🤖 ${msg.data}`]);
        } else if (msg.type === 'turn_complete') {
          setAiSpeaking(false);
        } else if (msg.type === 'error') {
          setTranscript(prev => [...prev, `❌ ${msg.data}`]);
          setState('error');
        }
      };

      ws.onerror = () => {
        setState('error');
        setTranscript(prev => [...prev, '❌ Connection error']);
      };

      ws.onclose = () => {
        if (state === 'connected') {
          setState('idle');
          setTranscript(prev => [...prev, '📴 Session ended']);
        }
      };
    } catch (e: any) {
      setState('error');
      setTranscript(prev => [...prev, `❌ ${e.message || 'Failed to connect'}`]);
    }
  }, [isMuted]);

  const disconnect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'end' }));
      wsRef.current.close();
    }
    wsRef.current = null;

    processorRef.current?.disconnect();
    processorRef.current = null;

    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;

    audioCtxRef.current?.close();
    audioCtxRef.current = null;

    playbackCtxRef.current?.close();
    playbackCtxRef.current = null;

    setState('idle');
    setAiSpeaking(false);
  }, []);

  const toggleMute = () => setIsMuted(!isMuted);

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      height: 420, borderRadius: 12,
      background: T.card, border: `1px solid ${T.border}`,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px', borderBottom: `1px solid ${T.border}`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: T.goldLight }}>
            🎤 Live Voice Director
          </span>
          <span style={{
            fontSize: 10, padding: '2px 8px', borderRadius: 10,
            background: state === 'connected' ? 'rgba(50,200,50,0.15)' : 'rgba(255,255,255,0.05)',
            color: state === 'connected' ? '#50c850' : T.dim,
            fontWeight: 600,
          }}>
            {state === 'idle' ? 'Ready' : state === 'connecting' ? 'Connecting...' : state === 'connected' ? 'Live' : 'Error'}
          </span>
          {aiSpeaking && (
            <Volume2 size={14} color={T.gold} style={{ animation: 'pulse 1s ease-in-out infinite' }} />
          )}
        </div>
      </div>

      {/* Transcript */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '16px',
        display: 'flex', flexDirection: 'column', gap: 8,
      }}>
        {state === 'idle' && transcript.length === 0 && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', height: '100%', gap: 12,
          }}>
            <div style={{
              width: 80, height: 80, borderRadius: '50%',
              background: 'rgba(212,168,67,0.08)', border: `2px solid ${T.border}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Mic size={32} color={T.dim} />
            </div>
            <p style={{ fontSize: 13, color: T.dim, textAlign: 'center', maxWidth: 280 }}>
              Talk to your AI creative director. Describe your story idea and they'll help shape it into a script.
            </p>
            <p style={{ fontSize: 11, color: T.dimmer }}>
              Powered by Gemini Live API
            </p>
          </div>
        )}

        {transcript.map((line, i) => (
          <p key={i} style={{
            fontSize: 12, lineHeight: 1.6, margin: 0,
            color: line.startsWith('🤖') ? T.goldLight : line.startsWith('❌') ? '#dc3232' : T.silverLight,
            padding: '6px 10px', borderRadius: 8,
            background: line.startsWith('🤖') ? 'rgba(212,168,67,0.06)' : 'rgba(255,255,255,0.02)',
          }}>
            {line}
          </p>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Controls */}
      <div style={{
        padding: '12px 16px', borderTop: `1px solid ${T.border}`,
        display: 'flex', justifyContent: 'center', gap: 12,
      }}>
        {state === 'idle' || state === 'error' ? (
          <button
            onClick={connect}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '12px 28px', borderRadius: 24,
              background: T.goldGrad, border: 'none',
              color: T.bg, fontSize: 14, fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 4px 16px rgba(212,168,67,0.3)',
            }}
          >
            <Phone size={18} /> Start Voice Session
          </button>
        ) : state === 'connecting' ? (
          <button disabled style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '12px 28px', borderRadius: 24,
            background: T.card, border: `1px solid ${T.border}`,
            color: T.dim, fontSize: 14, fontWeight: 600,
            cursor: 'default',
          }}>
            Connecting...
          </button>
        ) : (
          <>
            <button
              onClick={toggleMute}
              style={{
                width: 48, height: 48, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: isMuted ? 'rgba(220,50,50,0.15)' : 'rgba(255,255,255,0.06)',
                border: isMuted ? '1px solid rgba(220,50,50,0.3)' : `1px solid ${T.border}`,
                cursor: 'pointer',
              }}
              title={isMuted ? 'Unmute' : 'Mute'}
            >
              {isMuted ? <MicOff size={20} color="#dc3232" /> : <Mic size={20} color={T.gold} />}
            </button>
            <button
              onClick={disconnect}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '12px 28px', borderRadius: 24,
                background: 'rgba(220,50,50,0.15)',
                border: '1px solid rgba(220,50,50,0.3)',
                color: '#dc3232', fontSize: 14, fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <PhoneOff size={18} /> End Session
            </button>
          </>
        )}
      </div>

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
      `}</style>
    </div>
  );
}
