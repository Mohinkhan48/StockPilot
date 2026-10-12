# StockPilot Frontend

Modern, high-performance web client for StockPilot built with **React 19**, **TypeScript**, and **Vite**.

For comprehensive platform documentation, architecture specifications, API contracts, database setup, and test instructions, refer to the master [StockPilot README.md](../README.md).

---

## Quick Start

### 1. Install Dependencies
```bash
npm install
```

### 2. Development Server
```bash
npm run dev
```
Runs the Vite development server with Hot Module Replacement (HMR) at `http://localhost:5173/`.

### 3. Production Build & Type Checking
```bash
npm run build
```
Executes TypeScript compilation (`tsc -b`) followed by Vite production bundling into `dist/`.

### 4. Code Quality
```bash
npm run lint
```
Runs Oxlint across TypeScript and React source files.
