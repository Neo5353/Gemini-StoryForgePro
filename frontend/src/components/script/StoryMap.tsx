import { motion } from 'framer-motion';
import { MapPin, Clock, Users, Sparkles } from 'lucide-react';
import type { SceneBeat } from '../../types';

interface StoryMapProps {
  scenes: SceneBeat[];
  onSceneClick?: (scene: SceneBeat) => void;
}

const MOOD_COLORS: Record<string, string> = {
  tense: '#ef4444',
  happy: '#22c55e',
  sad: '#3b82f6',
  mysterious: '#8b5cf6',
  romantic: '#ec4899',
  action: '#f97316',
  calm: '#06b6d4',
  dark: '#6b7280',
};

function getMoodColor(mood: string): string {
  const key = mood.toLowerCase();
  return MOOD_COLORS[key] ?? '#a3a3a3';
}

export function StoryMap({ scenes, onSceneClick }: StoryMapProps) {
  if (scenes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-neutral-500">
        <Sparkles size={32} className="mb-3 opacity-50" />
        <p className="text-sm">Scene beats will appear here after script analysis</p>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Timeline spine */}
      <div className="absolute left-6 top-0 bottom-0 w-px bg-gradient-to-b from-neutral-700 via-neutral-600 to-neutral-700" />

      <div className="flex flex-col gap-4">
        {scenes.map((scene, idx) => {
          const moodColor = getMoodColor(scene.mood);
          return (
            <motion.div
              key={scene.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.08 }}
              onClick={() => onSceneClick?.(scene)}
              className="relative pl-14 cursor-pointer group"
            >
              {/* Timeline dot */}
              <div
                className="absolute left-4 top-4 w-5 h-5 rounded-full border-2 border-neutral-700 group-hover:scale-125 transition-transform"
                style={{ backgroundColor: moodColor }}
              />

              {/* Card */}
              <div className="p-4 rounded-xl bg-neutral-800/60 border border-neutral-700/50 hover:border-neutral-600 transition-all group-hover:bg-neutral-800">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-xs font-mono text-neutral-500 bg-neutral-700/50 px-2 py-0.5 rounded">
                    #{scene.scene_number}
                  </span>
                  <h4 className="text-sm font-semibold text-neutral-200">{scene.title}</h4>
                  <span
                    className="ml-auto text-xs px-2 py-0.5 rounded-full"
                    style={{ backgroundColor: `${moodColor}20`, color: moodColor }}
                  >
                    {scene.mood}
                  </span>
                </div>

                <p className="text-xs text-neutral-400 mb-3 line-clamp-2">{scene.description}</p>

                <div className="flex flex-wrap gap-3 text-xs text-neutral-500">
                  <span className="flex items-center gap-1">
                    <MapPin size={12} /> {scene.location}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock size={12} /> {scene.time_of_day}
                  </span>
                  {scene.characters.length > 0 && (
                    <span className="flex items-center gap-1">
                      <Users size={12} /> {scene.characters.join(', ')}
                    </span>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
