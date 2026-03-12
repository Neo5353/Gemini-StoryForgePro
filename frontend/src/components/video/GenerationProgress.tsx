import { motion } from 'framer-motion';
import { Loader2, Check, AlertCircle, Clock } from 'lucide-react';
import { useGenerationStore } from '../../stores/generationStore';
import type { GenerationStatus } from '../../types';

const STATUS_CONFIG: Record<GenerationStatus, {
  icon: typeof Loader2;
  color: string;
  bgColor: string;
  animate: boolean;
}> = {
  idle: { icon: Clock, color: '#737373', bgColor: '#26262620', animate: false },
  queued: { icon: Clock, color: '#a3a3a3', bgColor: '#40404020', animate: false },
  generating: { icon: Loader2, color: '#3b82f6', bgColor: '#3b82f620', animate: true },
  complete: { icon: Check, color: '#22c55e', bgColor: '#22c55e20', animate: false },
  error: { icon: AlertCircle, color: '#ef4444', bgColor: '#ef444420', animate: false },
};

export function GenerationProgress() {
  const { isGenerating, overallProgress, currentPhase, scenes } = useGenerationStore();

  if (!isGenerating && scenes.length === 0) return null;

  return (
    <div className="flex flex-col gap-4 p-5 rounded-xl bg-neutral-800/50 border border-neutral-700/50">
      {/* Overall progress */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-neutral-200">{currentPhase}</span>
          <span className="text-xs text-neutral-400">{Math.round(overallProgress)}%</span>
        </div>
        <div className="h-2 bg-neutral-700 rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{
              background: 'linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899)',
            }}
            initial={{ width: 0 }}
            animate={{ width: `${overallProgress}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
        </div>
      </div>

      {/* Per-scene progress */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {scenes.map((scene, i) => {
          const config = STATUS_CONFIG[scene.status];
          const Icon = config.icon;
          return (
            <motion.div
              key={scene.scene_id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.05 }}
              className="flex flex-col gap-2 p-3 rounded-lg border border-neutral-700/30"
              style={{ backgroundColor: config.bgColor }}
            >
              <div className="flex items-center gap-2">
                <Icon
                  size={14}
                  style={{ color: config.color }}
                  className={config.animate ? 'animate-spin' : ''}
                />
                <span className="text-xs text-neutral-300 truncate">Scene {i + 1}</span>
              </div>

              {/* Thumbnail preview */}
              {scene.thumbnail_url && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="aspect-video rounded overflow-hidden"
                >
                  <img
                    src={scene.thumbnail_url}
                    alt={`Scene ${i + 1}`}
                    className="w-full h-full object-cover"
                  />
                </motion.div>
              )}

              {/* Progress bar */}
              <div className="h-1 bg-neutral-700 rounded-full overflow-hidden">
                <motion.div
                  className="h-full rounded-full"
                  style={{ backgroundColor: config.color }}
                  animate={{ width: `${scene.progress}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>

              <span className="text-[10px] text-neutral-500">{scene.message}</span>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
