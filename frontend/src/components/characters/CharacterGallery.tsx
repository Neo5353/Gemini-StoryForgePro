import { useState } from 'react';
import { motion } from 'framer-motion';
import { Users } from 'lucide-react';
import { CharacterCard } from './CharacterCard';
import { CharacterEditor } from './CharacterEditor';
import type { CharacterRef } from '../../types';

interface CharacterGalleryProps {
  characters: CharacterRef[];
  projectId: string;
}

export function CharacterGallery({ characters, projectId }: CharacterGalleryProps) {
  const [editingCharacter, setEditingCharacter] = useState<CharacterRef | null>(null);

  if (characters.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-neutral-500">
        <Users size={32} className="mb-3 opacity-50" />
        <p className="text-sm">Characters will be extracted from your script</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-neutral-400">
          Characters · {characters.length}
        </h3>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {characters.map((char, i) => (
          <motion.div
            key={char.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
          >
            <CharacterCard
              character={char}
              onEdit={() => setEditingCharacter(char)}
            />
          </motion.div>
        ))}
      </div>

      {/* Editor modal */}
      {editingCharacter && (
        <CharacterEditor
          character={editingCharacter}
          projectId={projectId}
          onClose={() => setEditingCharacter(null)}
        />
      )}
    </div>
  );
}
