import js from '@eslint/js'
import ts from 'typescript-eslint'
import hooks from 'eslint-plugin-react-hooks'

export default ts.config(
  { ignores: ['dist/**', 'dist-demo/**', 'public/**', 'test-results/**', 'playwright-report/**'] },
  js.configs.recommended,
  ...ts.configs.recommended.map(config => ({ ...config, files: ['**/*.{ts,tsx}'] })),
  { files: ['tests/*.mjs', 'scripts/*.mjs'], languageOptions: { globals: { URL: 'readonly', process: 'readonly', Buffer: 'readonly', console: 'readonly', window: 'readonly', document: 'readonly', performance: 'readonly', self: 'readonly', Worker: 'writable', setTimeout: 'readonly', clearTimeout: 'readonly', innerWidth: 'readonly', innerHeight: 'readonly' } } },
  { files: ['src/workers/*.js'], languageOptions: { globals: { self: 'readonly', importScripts: 'readonly', URL: 'readonly' } } },
  { files: ['**/*.{ts,tsx}'], plugins: { 'react-hooks': hooks }, rules: {
    'react-hooks/rules-of-hooks': 'error',
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
  } },
)
