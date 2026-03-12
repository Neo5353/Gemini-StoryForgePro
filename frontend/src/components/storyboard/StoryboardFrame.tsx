import { motion } from 'framer-motion';
import { Camera, ArrowRight } from 'lucide-react';
import type { StoryboardFrameData, ShotType } from '../../types';

interface StoryboardFrameProps {
  frame: StoryboardFrameData;
  index: number;
}

const SHOT_COLORS: Record<ShotType, string> = {
  EWS: '#8b5cf6',
  WS: '#6366f1',
  FS: '#3b82f6',
  MS: '#06b6d4',
  MCU: '#14b8a6',
  CU: '#22c55e',
  ECU: '#eab308',
  OTS: '#f97316',
  POV: '#ef4444',
  AERIAL: '#a855f7',
};

const SHOT_LABELS: Record<ShotType, string> = {
  EWS: 'Extreme Wide',
  WS: 'Wide Shot',
  FS: 'Full Shot',
  MS: 'Medium Shot',
  MCU: 'Medium Close-Up',
  CU: 'Close-Up',
  ECU: 'Extreme Close-Up',
  OTS: 'Over the Shoulder',
  POV: 'Point of View',
  AERIAL: 'Aerial',
};

export function StoryboardFrame({ frame, index }: StoryboardFrameProps) {
  const shotColor = SHOT_COLORS[frame.shot_type];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="flex gap-4 group"
    >
      {/* Frame image */}
      <div className="relative w-64 shrink-0">
        <div className="aspect-video rounded-lg overflow-hidden border border-neutral-700/50 bg-neutral-900">
          {frame.image_url ? (
            <img src={frame.image_url} alt={`Frame ${frame.frame_number}`} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-neutral-800">
              <Camera size={24} className="text-neutral-600" />
            </div>
          )}
        </div>

        {/* Shot type badge */}
        <span
          className="absolute top-2 left-2 text-[10px] font-bold px-2 py-0.5 rounded-md text-white"
          style={{ backgroundColor: shotColor }}
        >
          {frame.shot_type}
        </span>

        {/* Frame number */}
        <span className="absolute bottom-2 right-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/60 text-neutral-300">
          #{frame.frame_number}
        </span>

        {/* Duration */}
        <span className="absolute bottom-2 left-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/60 text-neutral-300">
          {frame.duration_seconds}s
        </span>
      </div>

      {/* Annotations */}
      <div className="flex-1 min-w-0 py-1">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-xs font-medium text-neutral-300" style={{ color: shotColor }}>
            {SHOT_LABELS[frame.shot_type]}
          </span>
          <span className="text-neutral-600">·</span>
          <span className="text-xs text-neutral-500 flex items-center gap-1">
            <Camera size={11} /> {frame.camera_move}
          </span>
          <span className="text-neutral-600">·</span>
          <span className="text-xs text-neutral-500 flex items-center gap-1">
            <ArrowRight size={11} /> {frame.transition}
          </span>
        </div>

        {frame.dialogue && (
          <p className="text-xs text-neutral-400 italic mb-2 line-clamp-2">"{frame.dialogue}"</p>
        )}

        {frame.director_notes && (
          <p className="text-[11px] text-neutral-500 leading-relaxed">{frame.director_notes}</p>
        )}
      </div>
    </motion.div>
  );
}
