export interface EditablePreferences {
  theme: 'light' | 'dark';
  display_name_mode: 'zh_en' | 'en_zh' | 'zh' | 'en';
  auto_save_interval: number;
  sprite_zoom: number;
}
export type PreferencesPatch = Partial<EditablePreferences>;
export interface WorkbenchLayout {
  leftWidth: number | null;
  rightWidth: number | null;
  previewRatio: number | null;
  filesVisible: boolean;
  previewVisible: boolean;
}
/** Other legacy keys are preserved by Python, and are not editable here. */
export interface PreferencesState {
  revision: number;
  defaults: EditablePreferences & Record<string, unknown>;
  values: EditablePreferences & Record<string, unknown>;
  layout: WorkbenchLayout;
  warnings: string[];
}
export type PreferenceKey = keyof EditablePreferences;
