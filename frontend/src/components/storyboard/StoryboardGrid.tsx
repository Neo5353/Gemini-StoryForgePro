import { motion } from 'framer-motion';
import { Film } from 'lucide-react';
import { StoryboardFrame } from './StoryboardFrame';
import type { StoryboardFrameData } from '../../types';

interface StoryboardGridProps {
  frames: StoryboardFrameData[];
}

export function StoryboardGrid({ frames }: StoryboardGridProps) {
  if (frames.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-neutral-500">
        <Film size={32} className="mb-3 opacity-50" />
        <p className="text-sm">Storyboard frames will appear here after generation</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-neutral-400">
          Storyboard · {frames.length} frames
        </h3>
        <div className="flex items-center gap-2 text-xs text-neutral-500">
          <span>Total: {frames.reduce((a, f) => a + f.duration_seconds, 0)}s</span>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        {frames.map((frame, i) => (
          <motion.div key={frame.id}>
            <StoryboardFrame frame={frame} index={i} />
            {i < frames.length - 1 && (
              <div className="ml-32 mt-3 mb-1 h-px bg-neutral-800" />
            )}
          </motion.div>
        ))}
      </div>
    </div>
  );
}
