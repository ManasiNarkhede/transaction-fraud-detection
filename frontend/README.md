# Fraud Detection Guard — Frontend

React 18 + TypeScript + Vite frontend for the Real-Time Transaction Fraud Detection Guard.

## Tech Stack

- **React 18** — UI framework
- **TypeScript** — Type safety (strict mode)
- **Vite** — Build tool and dev server
- **Tailwind CSS** — Utility-first CSS
- **React Router** — Client-side routing
- **TanStack Query** — Server state management
- **Zustand** — Client state management
- **Axios** — HTTP client
- **Recharts** — Charts (Phase 10)
- **Vitest + Testing Library** — Unit testing
- **ESLint + Prettier** — Code quality

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── common/          # Generic UI primitives
│   │   └── layout/          # Header, Sidebar, Layout
│   ├── pages/               # Route-level components
│   ├── hooks/               # Custom React hooks
│   ├── stores/              # Zustand stores
│   ├── api/                 # API client
│   ├── types/               # TypeScript interfaces
│   ├── App.tsx              # Root component with routing
│   ├── main.tsx             # Entry point
│   └── index.css            # Tailwind directives
├── tests/                   # Test suite
├── index.html               # HTML entry point
├── vite.config.ts           # Vite configuration
├── tsconfig.json            # TypeScript configuration
├── tailwind.config.js       # Tailwind CSS configuration
└── package.json             # Dependencies
```

## Getting Started

### Prerequisites

- Node.js >= 20
- npm

### Install Dependencies

```bash
npm install
```

### Environment Variables

Create a `.env` file in the `frontend/` directory:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

### Run Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

### Build for Production

```bash
npm run build
```

### Run Tests

```bash
npm test
```

### Lint and Format

```bash
npm run lint
npm run format
```
