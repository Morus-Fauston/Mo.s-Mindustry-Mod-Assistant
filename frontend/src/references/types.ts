export interface ReferenceCandidate {
  value: string;
  category: string;
  label: string;
  isProject: boolean;
}

export interface ReferenceResult {
  candidates: ReferenceCandidate[];
  categories: { id: string; label: string }[];
  current: { value: string | null; label: string; known: boolean };
}
