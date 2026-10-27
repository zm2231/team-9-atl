import type { Category } from "../../lib/types";

const CATEGORIES: Category[] = [1, 2, 3, 4, 5];

export default function CategoryPicker({
  value,
  onChange,
  disabled,
}: {
  value: Category;
  onChange: (c: Category) => void;
  disabled?: boolean;
}) {
  return (
    <span className="seg" role="group" aria-label="Hurricane category">
      {CATEGORIES.map((c) => (
        <button key={c} type="button" aria-pressed={value === c} disabled={disabled} onClick={() => onChange(c)}>
          Cat {c}
        </button>
      ))}
    </span>
  );
}
