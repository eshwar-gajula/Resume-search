# Frontend

The frontend uses Next.js App Router. The full Windows setup guide is in the root [README](../README.md).

## Run manually

From PowerShell in this directory:

```powershell
npm ci
npm run dev -- --hostname 127.0.0.1
```

Open `http://127.0.0.1:3000`. The backend must be running at `http://127.0.0.1:8010`.

To change the API URL, set `NEXT_PUBLIC_API_URL` in a local `.env.local` file, for example:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8010/api
```

Restart the frontend after changing this setting.

## Production build

```powershell
npm run build
npm start -- --hostname 127.0.0.1
```
