import { motion } from 'framer-motion';
import type { SceneChapter } from '../../types';

interface TimelineProps {
  chapters: SceneChapter[];
  totalDuration: number;
  currentTime: number;
  onSeek: (time: number) => void;
}

export function Timeline({ chapters, totalDuration, currentTime, onSeek }: TimelineProps) {
  if (chapters.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 p-4 rounded-xl bg-neutral-800/30 border border-neutral-700/30">
      <h4 className="text-xs font-medium text-neutral-500 mb-1">Timeline</h4>

      {/* Bar */}
      <div className="relative h-12 bg-neutral-800 rounded-lg overflow-hidden">
        {chapters.map((chapter, i) => {
          const left = (chapter.start_time / totalDuration) * 100;
          const width = ((chapter.end_time - chapter.start_time) / totalDuration) * 100;
          const isActive = currentTime >= chapter.start_time && currentTime < chapter.end_time;
          const hue = (i * 360) / chapters.length;

          return (
            <motion.button
              key={chapter.scene_id}
              onClick={() => onSeek(chapter.start_time)}
              className="absolute top-0 h-full flex items-center justify-center text-[9px] text-white/70 hover:text-white font-medium border-r border-neutral-700/50 transition-all overflow-hidden"
              style={{
                left: `${left}%`,
                width: `${width}%`,
                backgroundColor: isActive ? `hsla(${hue}, 60%, 40%, 0.6)` : `hsla(${hue}, 40%, 25%, 0.4)`,
              }}
              whileHover={{ backgroundColor: `hsla(${hue}, 60%, 45%, 0.7)` }}
            >
              {chapter.thumbnail_url && (
                <img
                  src={chapter.thumbnail_url}
                  alt=""
                  className="absolute inset-0 w-full h-full object-cover opacity-30"
                />
              )}
              <span className="relative z-10 truncate px-1">{chapter.title}</span>
            </motion.button>
          );
        })}

        {/* Playhead */}
        <motion.div
          className="absolute top-0 h-full w-0.5 bg-white shadow-lg z-20"
          style={{ left: `${(currentTime / totalDuration) * 100}%` }}
          animate={{ left: `${(currentTime / totalDuration) * 100}%` }}
          transition={{ duration: 0.1 }}
        />
      </div>
    </div>
  );
}
