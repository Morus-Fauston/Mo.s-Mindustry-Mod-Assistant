import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  workers: 1,
  fullyParallel: false,
  reporter: [['list'], ['json', { outputFile: 'test-results/host-results.json' }]],
  projects: [
    { name: 'host', testMatch: ['startup.spec.ts', 'workspace.spec.ts', 'editing.spec.ts', 'preview.spec.ts', 'forms.spec.ts', 'references.spec.ts', 'resources.spec.ts', 'nested.spec.ts'] },
    { name: 'package', testMatch: 'package.spec.ts' },
  ],
});
