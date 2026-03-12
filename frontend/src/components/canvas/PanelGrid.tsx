import { motion } from 'framer-motion';
import { Grid2X2, Grid3X3, Maximize, Rows3 } from 'lucide-react';
import type { GridLayout } from '../../types';

interface PanelGridProps {
  selected: GridLayout;
  onChange: (layout: GridLayout) => void;
}

interface LayoutOption {
  id: GridLayout;
  label: string;
  icon: typeof Grid2X2;
  preview: number[][]; // 1s and 0s representing filled cells
}

const LAYOUTS: LayoutOption[] = [
  { id: '2x2', label: '2×2', icon: Grid2X2, preview: [[1, 1], [1, 1]] },
  { id: '3x2', label: '3×2', icon: Grid3X3, preview: [[1, 1, 1], [1, 1, 1]] },
  { id: '2x3', label: '2×3', icon: Grid2X2, preview: [[1, 1], [1, 1], [1, 1]] },
  { id: '3x3', label: '3×3', icon: Grid3X3, preview: [[1, 1, 1], [1, 1, 1], [1, 1, 1]] },
  { id: 'splash', label: 'Splash', icon: Maximize, preview: [[1]] },
  { id: 'vertical_strip', label: 'Strip', icon: Rows3, preview: [[1], [1], [1], [1]] },
];

function GridPreview({ grid, active }: { grid: number[][]; active: boolean }) {
  return (
    <div className="flex flex-col gap-0.5" style={{ width: 28, height: 36 }}>
      {grid.map((row, ri) => (
        <div key={ri} className="flex gap-0.5 flex-1">
          {row.map((cell, ci) => (
            <div
              key={ci}
              className={`flex-1 rounded-[2px] ${
                active ? 'bg-white/40' : 'bg-neutral-600'
              }`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function PanelGrid({ selected, onChange }: PanelGridProps) {
  return (
    <div className="flex gap-2 flex-wrap">
      {LAYOUTS.map((layout) => {
        const isActive = selected === layout.id;
        return (
          <motion.button
            key={layout.id}
            onClick={() => onChange(layout.id)}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={`flex flex-col items-center gap-1.5 p-3 rounded-lg border transition-all ${
              isActive
                ? 'bg-white/10 border-white/25 text-white'
                : 'bg-neutral-800/40 border-neutral-700/50 text-neutral-500 hover:text-neutral-300'
            }`}
          >
            <GridPreview grid={layout.preview} active={isActive} />
            <span className="text-[10px] font-medium">{layout.label}</span>
          </motion.button>
        );
      })}
    </div>
  );
}
