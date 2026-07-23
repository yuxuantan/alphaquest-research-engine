# AlphaQuest Research Studio UI

React 19 and TypeScript presentation layer for the local AlphaQuest FastAPI
service. Research governance remains in the Python service layer; this client
does not reproduce publication, approval, or result-verdict logic.

## Development

```bash
cd studio-ui
npm ci
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8501` during development.

## Checks and production build

```bash
npm run check
npm test
npm run build
```

The production build writes directly to
`src/alphaquest/studio/web_assets/`. Commit `index.html` and `assets/*` whenever
UI source changes. The FastAPI application serves this
bundle and provides history-route fallback, so the researcher does not need
Node at runtime.

All fonts, icons, JavaScript, and CSS are bundled locally. The UI has no CDN or
remote runtime dependency.
