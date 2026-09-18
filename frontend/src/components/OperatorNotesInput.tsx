import { Plus, Trash2, MessageSquareText } from 'lucide-react';

interface OperatorNotesInputProps {
  notes: string[];
  onChange: (notes: string[]) => void;
  maxNotes?: number;
}

export default function OperatorNotesInput({
  notes,
  onChange,
  maxNotes = 3,
}: OperatorNotesInputProps) {
  const addNote = () => {
    if (notes.length < maxNotes) {
      onChange([...notes, '']);
    }
  };

  const updateNote = (index: number, value: string) => {
    const updated = [...notes];
    updated[index] = value;
    onChange(updated);
  };

  const removeNote = (index: number) => {
    onChange(notes.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm font-semibold text-surface-700 dark:text-surface-300">
          <MessageSquareText className="w-4 h-4 text-grid-500" />
          Operator Notes
        </label>
        <span className="text-xs text-surface-400">
          {notes.length}/{maxNotes}
        </span>
      </div>

      <div className="space-y-2">
        {notes.map((note, index) => (
          <div key={index} className="flex gap-2 animate-fade-in">
            <div className="flex items-center justify-center w-6 h-9 text-xs font-mono font-bold text-surface-400 dark:text-surface-500">
              {index + 1}
            </div>
            <input
              type="text"
              value={note}
              onChange={(e) => updateNote(index, e.target.value)}
              placeholder={`Operator directive ${index + 1}…`}
              className="input-field flex-1"
            />
            <button
              onClick={() => removeNote(index)}
              className="p-2 rounded-lg text-surface-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors cursor-pointer"
              title="Remove note"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {notes.length < maxNotes && (
        <button
          onClick={addNote}
          className="btn-secondary w-full text-sm"
        >
          <Plus className="w-4 h-4" />
          Add Operator Note
        </button>
      )}
    </div>
  );
}
