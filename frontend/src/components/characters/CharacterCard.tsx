import { motion } from 'framer-motion';
import { Edit3, User } from 'lucide-react';
import type { CharacterRef } from '../../types';

interface CharacterCardProps {
  character: CharacterRef;
  onEdit?: () => void;
}

export function CharacterCard({ character, onEdit }: CharacterCardProps) {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="group relative flex flex-col rounded-xl overflow-hidden border border-neutral-700/50 bg-neutral-800/50 hover:border-neutral-600 transition-colors"
    >
      {/* Ref sheet / thumbnail */}
      <div className="relative aspect-[3/4] bg-neutral-900">
        {character.ref_sheet_url ? (
          <img
            src={character.ref_sheet_url}
            alt={character.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <User size={48} className="text-neutral-700" />
          </div>
        )}

        {/* Edit button */}
        {onEdit && (
          <button
            onClick={onEdit}
            className="absolute top-2 right-2 p-1.5 rounded-lg bg-black/60 text-white/60 hover:text-white opacity-0 group-hover:opacity-100 transition-all"
          >
            <Edit3 size={14} />
          </button>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <h4 className="text-sm font-semibold text-neutral-200 mb-1">{character.name}</h4>
        <p className="text-xs text-neutral-500 line-clamp-2 mb-2">{character.description}</p>

        {/* Expressions */}
        {character.expressions.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {character.expressions.map((expr) => (
              <span
                key={expr}
                className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-neutral-500"
              >
                {expr}
              </span>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
