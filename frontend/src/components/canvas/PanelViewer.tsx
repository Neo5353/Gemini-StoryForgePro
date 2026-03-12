import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft, ChevronRight, Maximize2 } from 'lucide-react';
import { PanelCanvas } from './PanelCanvas';
import type { PageData } from '../../types';

interface PanelViewerProps {
  pages: PageData[];
}

export function PanelViewer({ pages }: PanelViewerProps) {
  const [currentPage, setCurrentPage] = useState(0);

  if (pages.length === 0) {
    return (
      <div className="flex items-center justify-center h-96 rounded-xl border border-neutral-700/50 bg-neutral-900/50">
        <p className="text-neutral-500 text-sm">No pages generated yet</p>
      </div>
    );
  }

  const page = pages[currentPage];
  const hasPrev = currentPage > 0;
  const hasNext = currentPage < pages.length - 1;

  return (
    <div className="flex flex-col gap-4">
      {/* Page viewer */}
      <div className="relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={page.id}
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -50 }}
            transition={{ duration: 0.3 }}
          >
            <PanelCanvas page={page} />
          </motion.div>
        </AnimatePresence>

        {/* Nav arrows */}
        {hasPrev && (
          <button
            onClick={() => setCurrentPage((p) => p - 1)}
            className="absolute left-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-black/60 text-white/70 hover:text-white hover:bg-black/80 transition-all"
          >
            <ChevronLeft size={24} />
          </button>
        )}
        {hasNext && (
          <button
            onClick={() => setCurrentPage((p) => p + 1)}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-black/60 text-white/70 hover:text-white hover:bg-black/80 transition-all"
          >
            <ChevronRight size={24} />
          </button>
        )}
      </div>

      {/* Page indicators */}
      <div className="flex items-center justify-center gap-3">
        <span className="text-xs text-neutral-500">
          Page {currentPage + 1} of {pages.length}
        </span>
        <div className="flex gap-1.5">
          {pages.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrentPage(i)}
              className={`w-2 h-2 rounded-full transition-all ${
                i === currentPage ? 'bg-white w-6' : 'bg-neutral-600 hover:bg-neutral-400'
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
