import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  workers: 1,
  fullyParallel: false,
  reporter: [['list'], ['json', { outputFile: 'test-results/host-results.json' }]],
  projects: [
    { name: 'host', testMatch: ['startup.spec.ts', 'workspace.spec.ts', 'editing.spec.ts', 'preview.spec.ts', 'forms.spec.ts', 'references.spec.ts', 'resources.spec.ts', 'nested.spec.ts', 'resource-fields.spec.ts', 'abilities.spec.ts', 'weapons.spec.ts', 'research.spec.ts', 'source.spec.ts', 'layers.spec.ts', 'validation.spec.ts', 'dynamic-preview.spec.ts', 'generation.spec.ts', 'content.spec.ts'] },
    { name: 'comparison-host', testMatch: 'comparison.spec.ts' },
    { name: 'preferences-host', testMatch: ['preferences.spec.ts', 'preferences-restart.spec.ts', 'preferences-recovery.spec.ts'] },
    { name: 'dpi-host', testMatch: 'dpi-matrix.spec.ts', retries: 0 },
    { name: 'acceptance-journey-host', testMatch: 'acceptance-journey.spec.ts', retries: 0 },
    { name: 'combined-regression-host', testMatch: 'combined-regression.spec.ts', retries: 0 },
    { name: 'legacy-entrypoints-host', testMatch: 'legacy-entrypoints.spec.ts', retries: 0 },
    { name: 'package', testMatch: 'package.spec.ts' },
  ],
});
