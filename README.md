# StockPilot — Multi-Tenant Inventory & Sales Order Management System

StockPilot is a full-stack, enterprise-grade inventory and sales order management platform built with a **Django REST Framework (DRF)** backend, a **React 19 + TypeScript + Vite** frontend, and a **MySQL** relational database.

The system is designed with strict multi-tenant workspace isolation, server-authoritative pricing, atomic database transactions with concurrency row-locking, append-only inventory movement audit logs, and role-based permissions (Workspace Owner vs. Staff).

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture & Tech Stack](#architecture--tech-stack)
- [Multi-Tenant Workspace Isolation](#multi-tenant-workspace-isolation)
- [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
- [Inventory Transaction Strategy & Atomicity](#inventory-transaction-strategy--atomicity)
- [Order Lifecycle & Pricing Integrity](#order-lifecycle--pricing-integrity)
- [Environment Variables & Configuration](#environment-variables--configuration)
- [Database Migrations & Fresh Initialization](#database-migrations--fresh-initialization)
- [Local Setup & Installation Instructions](#local-setup--installation-instructions)
- [API Endpoints Documentation](#api-endpoints-documentation)
- [Automated Test Suite & Verification](#automated-test-suite--verification)
- [AI Assistance Disclosure](#ai-assistance-disclosure)
- [Submission & Deployment Readiness Status](#submission--deployment-readiness-status)

---

## Project Overview

Managing inventory and sales orders across distinct client accounts or business units requires absolute tenant segregation, zero data leakage, and rigorous mathematical and transactional consistency. StockPilot delivers:

1. **Multi-Tenant Workspaces**: Users can create or belong to multiple isolated workspaces. Data in Workspace A is strictly partitioned from Workspace B.
2. **Server-Authoritative Pricing**: The frontend never dictates prices or totals. Pricing snapshots remain decoupled until order confirmation.
3. **Atomic Stock Control**: Order confirmations lock rows in ascending primary-key order to eliminate race conditions and deadlocks, ensuring that multi-item transactions commit entirely or abort with zero partial stock deductions.
4. **Append-Only Audit Ledger**: Every inventory transition (restock, sale, adjustment, return) generates an immutable `InventoryMovement` log entry that can never be modified or deleted.
5. **Real-Time Workspace Metrics**: Workspace dashboard statistics are calculated in single server-side SQL aggregate queries across all active catalog products rather than deriving numbers from a single paginated page.

---

## Architecture & Tech Stack

### Backend
- **Framework**: Django 5.2.18
- **API Engine**: Django REST Framework (DRF) 3.18.3
- **Authentication**: TokenAuthentication (`rest_framework.authtoken`) with session support
- **CORS Support**: `django-cors-headers` 4.9.0
- **Database Connector**: `mysqlclient` 2.3.0

### Frontend
- **Framework**: React 19.2.8
- **Build Tool**: Vite 8.3.4 (with `@vitejs/plugin-react`)
- **Language**: TypeScript 6.0.2 (strict mode enabled)
- **Routing**: React Router DOM 7.18.4
- **HTTP Client**: Axios 1.20.0 (with request interceptors for token attachment)
- **Icons**: Lucide React 1.55.0
- **Styling**: Vanilla CSS design system (tokens, glassmorphism, responsive navigation)

### Database
- **Engine**: MySQL 8.x
- **Character Set**: `utf8mb4` with `utf8mb4_unicode_ci`
- **Application Database**: `stockpilot_app`
- **Isolated Test Database**: `test_stockpilot_app` (managed automatically by Django test runner)

---

## Multi-Tenant Workspace Isolation

Multi-tenancy in StockPilot is implemented with workspace scoping enforced at both the database and view layers:

- **Strict URL Scoping**: Every workspace resource path contains `workspaces/<workspace_id>/`.
- **Queryset Boundary**: Views inherit from `WorkspaceContextMixin`, which validates that `request.user` has an active `WorkspaceMembership` in the specified `workspace_id`.
- **Anti-Enumeration Defense**: If an authenticated user queries a workspace ID they do not belong to, the server returns `404 Not Found` rather than `403 Forbidden`, preventing workspace existence probing.
- **Cross-Workspace Relation Protection**: When creating order lines, products referenced must belong to the active workspace. Cross-workspace product IDs submitted in order payloads are rejected with validation errors.
- **Object Resolution Filtering**: Direct object lookups (`/products/<pk>/`, `/orders/<pk>/`) filter on both `pk` and `workspace`. Supplying a valid ID from a different workspace returns `404 Not Found`.

---

## Role-Based Access Control (RBAC)

Each workspace member holds either the **Owner** or **Staff** role, governed by `accounts.permissions`:

| Capability | Workspace Owner | Workspace Staff | Non-Member / Outsider |
|---|:---:|:---:|:---:|
| View products, stock, & audit movements | Yes | Yes | 404 Not Found |
| Restock & perform manual stock adjustments | Yes | Yes | 404 Not Found |
| Create orders & confirm/complete/cancel orders | Yes | Yes | 404 Not Found |
| View workspace aggregate stats & low-stock alerts | Yes | Yes | 404 Not Found |
| Create products | Yes | Yes | 404 Not Found |
| Update product details (name, price, threshold) | Yes | Yes | 404 Not Found |
| Delete products | **Yes** | **No (403 Forbidden)** | 404 Not Found |
| Delete draft (pending) orders | **Yes** | **No (403 Forbidden)** | 404 Not Found |
| Add new members or remove staff members | **Yes** | **No (403 Forbidden)** | 404 Not Found |
| Update workspace metadata or delete workspace | **Yes** | **No (403 Forbidden)** | 404 Not Found |

> **Note**: Primary workspace owners cannot be removed from their own workspaces to prevent orphaned tenants.

---

## Inventory Transaction Strategy & Atomicity

StockPilot protects inventory levels against race conditions, negative inventory, and partial failures:

### 1. Database Row Locking (`select_for_update`)
During order confirmation, order cancellation, and stock adjustments, the system acquires row-level locks via PostgreSQL/MySQL `SELECT ... FOR UPDATE`:
```python
# Products are always locked in deterministic ascending PK order to prevent deadlocks:
for item in self.items.select_related('product').order_by('product_id'):
    product = Product.objects.select_for_update().get(pk=item.product_id)
```

### 2. Multi-Item All-or-Nothing Atomicity
Order confirmation runs within `@transaction.atomic`. Before updating any inventory, the system validates stock across **all items** in the order. If even a single item exceeds available inventory:
- `InsufficientStockError` is raised.
- The transaction completely rolls back.
- Zero stock quantities change.
- No partial `sale` movements are written.
- The order remains safely in `pending` status.

### 3. Database Check Constraints
Non-negativity is enforced directly by MySQL table check constraints:
- `product_stock_nonneg`: `stock_quantity >= 0`
- `product_price_nonneg`: `price >= 0`
- `product_low_stock_threshold_nonneg`: `low_stock_threshold >= 0`
- `orderitem_qty_positive`: `quantity >= 1`
- `orderitem_price_nonneg`: `unit_price >= 0` (when stamped)

### 4. Append-Only Audit Ledger
`InventoryMovement` instances record every stock modification with:
- `movement_type`: `restock`, `sale`, `adjustment`, or `return`.
- Signed `quantity`: positive for stock additions; negative for stock reductions.
- `resulting_stock`: snapshot of stock quantity immediately after the operation.
- `created_by`: foreign key to the user who initiated the action.
- `created_at`: immutable UTC timestamp.
Any call to `.save()` on an existing `InventoryMovement` raises `ValueError`, guaranteeing immutability.

---

## Order Lifecycle & Pricing Integrity

An Order progresses through defined status states:

```
[ PENDING ] ────── confirm() ──────► [ CONFIRMED ] ────── complete() ──────► [ COMPLETED ]
     │                                     │
     └─────────── cancel() ─────────┬──────┘
                                    ▼
                              [ CANCELLED ]
```

### Order States:
1. **Pending**: Draft state.
   - Products and quantities are specified.
   - **No stock is deducted**.
   - `OrderItem.unit_price`, `product_name`, and `product_sku` remain `NULL`/blank.
   - Estimated totals (`estimated_line_total`, `estimated_total`) are calculated on the fly using current live product prices.
   - The UI displays an amber indicator with *"Prices lock upon confirmation"*.
2. **Confirmed**: Active sales order.
   - Validates all stock availability.
   - Deducts stock atomically for all items.
   - Writes `sale` movements in the audit ledger.
   - Stamps immutable snapshot values onto `OrderItem` (`unit_price = product.price`, `product_name = product.name`, `product_sku = product.sku`).
   - If products are later renamed, repriced, or marked inactive, confirmed orders preserve exact historical prices and totals.
3. **Completed**: Final delivered state.
   - Terminal state. No inventory changes occur at completion since stock was already dispatched on confirmation.
4. **Cancelled**: Terminal aborted state.
   - If cancelled from `Pending`: Status updates to `cancelled`; no stock was ever held, so no stock changes occur.
   - If cancelled from `Confirmed`: Stock for each item is restored atomically, and `return` inventory movements are written to the audit ledger.
   - **Cancellation Idempotency**: Repeated cancellation requests on an already cancelled order are safely blocked with `InvalidTransitionError` and never restore inventory twice.

---

## Environment Variables & Configuration

StockPilot reads configuration from environment variables. A template is provided in [`StockPilot/.env.example`](file:///c:/Users/User/OneDrive/Documents/Desktop/StockPilot/StockPilot/.env.example):

```env
# Django Security
DJANGO_SECRET_KEY=replace-me-with-a-long-random-string
DEBUG=False
ALLOWED_HOSTS=127.0.0.1,localhost

# MySQL Database Configuration
DB_NAME=stockpilot_app
DB_USER=root
DB_PASSWORD=replace-me
DB_HOST=127.0.0.1
DB_PORT=3306

# Frontend CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173
```

> **Security Guarantee**: Real credentials must reside in `StockPilot/.env`. The `.env` file, virtual environments (`venv/`), build artifacts (`dist/`), and dependencies (`node_modules/`) are strictly excluded from Git tracking via `.gitignore`. Never commit secrets to version control.

---

## Database Migrations & Fresh Initialization

StockPilot maintains a linear, consistent migration history that cleanly handles circular foreign key dependencies between inventory movements and orders:

1. **`accounts.0001_initial`**: Creates `Workspace` and `WorkspaceMembership` tables with unique user-workspace constraints.
2. **`inventory.0001_initial`**: Creates `Product` and `InventoryMovement` base models.
3. **`orders.0001_initial`**: Creates `Order` and `OrderItem` models referencing `Workspace` and `Product`.
4. **`inventory.0002_initial`**: Links `InventoryMovement.order` foreign key to `Order` and applies product SKU uniqueness per workspace.
5. **`inventory.0003_product_product_stock_nonneg_and_more`**: Enforces non-negative DB check constraints on products.

### Initializing a Fresh Database:
```sql
-- In MySQL shell:
CREATE DATABASE stockpilot_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
Then run:
```bash
python manage.py migrate
```
Django will execute all migrations across `accounts`, `inventory`, and `orders` without conflict.

---

## Local Setup & Installation Instructions

### Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: 18.x or higher (npm 9+)
- **MySQL Server**: 8.0 or higher running on port 3306

---

### Step 1: Backend Setup

1. Open PowerShell / Terminal in the repository root and navigate to `StockPilot/`:
   ```bash
   cd StockPilot
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # On Linux / macOS:
   source venv/bin/activate
   ```
3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Open `.env` in a text editor and update `DJANGO_SECRET_KEY`, `DB_USER`, and `DB_PASSWORD`.
5. Run migrations:
   ```bash
   python manage.py migrate
   ```
6. (Optional) Create a superuser for administrative portal access (`/admin/`):
   ```bash
   python manage.py createsuperuser
   ```
7. Launch the development server:
   ```bash
   python manage.py runserver 127.0.0.1:8000
   ```
   Backend will be running at `http://127.0.0.1:8000/`.

---

### Step 2: Frontend Setup

1. In a separate terminal, navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install frontend dependencies:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
4. Access the web application at `http://localhost:5173/`.

---

## API Endpoints Documentation

All API endpoints are prefixed with `/api/`. Unauthenticated requests to protected endpoints return `401 Unauthorized`. Requests accessing resources outside the user's workspace return `404 Not Found`.

### Authentication Endpoints (`/api/auth/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/auth/register/` | Public | Register new user account; returns auth token & user profile |
| `POST` | `/api/auth/login/` | Public | Login with username/password; returns auth token |
| `POST` | `/api/auth/logout/` | Authenticated | Revoke and delete current user's auth token |
| `GET` | `/api/auth/me/` | Authenticated | Retrieve current user profile and list of joined workspaces |

### Workspace Endpoints (`/api/workspaces/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/api/workspaces/` | Authenticated | List all workspaces current user belongs to |
| `POST` | `/api/workspaces/` | Authenticated | Create a new workspace (creator automatically becomes Owner) |
| `GET` | `/api/workspaces/<id>/` | Member | Retrieve details of a specific workspace |
| `PUT`/`PATCH` | `/api/workspaces/<id>/` | Owner | Update workspace name/details |
| `DELETE` | `/api/workspaces/<id>/` | Owner | Delete workspace and all contained data |
| `GET` | `/api/workspaces/<id>/members/` | Member | List all members and their roles in workspace |
| `POST` | `/api/workspaces/<id>/members/` | Owner | Add existing user to workspace as Staff or Owner |
| `DELETE` | `/api/workspaces/<id>/members/<user_id>/` | Owner | Remove user from workspace (primary owner cannot be removed) |

### Products & Inventory Endpoints (`/api/workspaces/<id>/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `.../products/` | Member | List products with search (`?search=`), pagination, and filters (`?is_active=`, `?low_stock=`) |
| `POST` | `.../products/` | Member | Create a new product in the workspace |
| `GET` | `.../products/<pk>/` | Member | Retrieve product details |
| `PUT`/`PATCH` | `.../products/<pk>/` | Member | Update product information (price, name, low-stock threshold, active status) |
| `DELETE` | `.../products/<pk>/` | Owner | Permanently delete product |
| `GET` | `.../products/low-stock/` | Member | List products where `stock_quantity <= low_stock_threshold` |
| `POST` | `.../products/<pk>/restock/` | Member | Increase stock (`{"quantity": N, "notes": "..."}`) with audit log |
| `POST` | `.../products/<pk>/adjust/` | Member | Manually adjust stock (`{"quantity": ±N, "notes": "mandatory"}`) |
| `GET` | `.../products/<pk>/movements/` | Member | Retrieve append-only audit trail for specific product |
| `GET` | `.../inventory/movements/` | Member | Retrieve workspace-wide audit logs with filters (`?movement_type=`, `?product_id=`) |
| `GET` | `.../inventory/stats/` | Member | Single SQL aggregation returning `total_products`, `total_active_products`, `total_stock_units`, and `low_stock_count` |

### Orders Endpoints (`/api/workspaces/<id>/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `.../orders/` | Member | List orders with pagination, filtering (`?status=`), and ordering (`?ordering=`) |
| `POST` | `.../orders/` | Member | Create a draft pending order with multiple items |
| `GET` | `.../orders/<pk>/` | Member | Retrieve order details with items, snapshots, and estimated/confirmed totals |
| `DELETE` | `.../orders/<pk>/` | Owner | Delete draft `pending` order (confirmed orders cannot be deleted; must cancel) |
| `POST` | `.../orders/<pk>/confirm/` | Member | Transition `pending` → `confirmed`: lock rows, deduct stock atomically, write sales logs, stamp price snapshots |
| `POST` | `.../orders/<pk>/complete/` | Member | Transition `confirmed` → `completed` (terminal state) |
| `POST` | `.../orders/<pk>/cancel/` | Member | Transition order to `cancelled`; restores inventory and writes return movements if order was confirmed |

---

## Automated Test Suite & Verification

StockPilot includes a test suite of **123 automated tests** spanning unit, model constraint, API integration, multi-tenant isolation, role authorization, and concurrency testing.

### Test Categories:
1. **Accounts & RBAC Tests (`accounts/`)**:
   - User registration, token generation, login, logout, and token revocation.
   - Workspace creation and auto-assignment of creator as Owner.
   - Role enforcement (Staff blocked from deleting products, deleting draft orders, and managing members).
   - Cross-workspace 404 anti-enumeration protections.
2. **Inventory & Movement Tests (`inventory/`)**:
   - Product SKU uniqueness enforced per workspace (same SKU allowed across different workspaces).
   - Non-negative stock and price database constraints.
   - Immutability of `InventoryMovement` records (append-only ledger).
   - Validations rejecting 0 or negative restocking quantities.
   - Stock adjustments rejecting deductions that would yield negative stock.
   - Single-query aggregate statistics endpoint verification (`/inventory/stats/`).
   - Multi-threaded concurrent order confirmation preventing overselling.
3. **Orders & Pricing Tests (`orders/`)**:
   - Server-authoritative pricing rejection: client-submitted `unit_price`, line totals, or order totals are discarded.
   - Estimated total calculation for pending orders ($599 mouse × 2 = $1,198 estimated total; unit_price remains NULL).
   - Atomic confirmation: Multi-item orders where one item lacks sufficient stock roll back completely with zero deductions.
   - Price and name snapshots remaining immutable after products are modified or deleted.
   - Order lifecycle transitions (`pending` → `confirmed` → `completed`).
   - Idempotent cancellation: Cancelling an order twice raises `InvalidTransitionError` and restores inventory exactly once.

### Running Backend Tests:
Activate the virtual environment, load the environment variables, and run:
```powershell
& .\venv\Scripts\Activate.ps1
Get-Content .env | ForEach-Object { if ($_ -match '^\s*([^#][^=]+)=(.*)$') { [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process') } }
python manage.py test --verbosity=2
```
**Verification Result**:
```text
Ran 123 tests in 159.345s
OK
Destroying test database for alias 'default' ('test_stockpilot_app')...
```

### Running Frontend Type-Check & Build:
From the `frontend/` directory:
```bash
npm run build
```
**Verification Result**:
```text
> frontend@0.0.0 build
> tsc -b && vite build

vite v8.3.4 building client environment for production...
✓ 1991 modules transformed.
dist/index.html                   0.76 kB │ gzip:   0.43 kB
dist/assets/index-SMAOuOxD.css    6.02 kB │ gzip:   1.79 kB
dist/assets/index-NzsW7rIv.js   389.42 kB │ gzip: 115.95 kB
✓ built in 641ms
```

---

## AI Assistance Disclosure

In accordance with academic and assessment transparency guidelines:

- **AI Tools Used**: Google DeepMind Antigravity AI agentic coding assistant powered by Gemini.
- **Scope of AI Assistance**:
  - Architectural review and threat modeling for multi-tenant isolation and anti-enumeration defenses.
  - Designing row-locking concurrency control (`select_for_update`) to prevent inventory overselling and deadlocks.
  - Formulating server-authoritative pricing flow with deferred snapshots and estimated totals.
  - Implementing the server-side aggregate statistics endpoint (`WorkspaceInventoryStatsView`).
  - Expanding the automated test suite to 123 tests, specifically boundary condition, regression, and concurrency test cases.
  - Codebase auditing, migration integrity checking, and documentation synthesis.
- **Human Author Accountability**: All architecture decisions, domain schemas, business logic implementations, and test assertions were reviewed, executed, verified, and validated for correctness.

---

## Submission & Deployment Readiness Status

### Completed Deliverables (Verified Locally):
- [x] **Backend Implementation**: Fully functional Django REST Framework API with token authentication, multi-tenancy, and RBAC.
- [x] **Frontend Implementation**: Modern React 19 + TypeScript + Vite UI with comprehensive workspace, product, inventory, and order views.
- [x] **Database Schema & Migrations**: Complete migration graph with MySQL constraints, tested and verified on `stockpilot_app`.
- [x] **Test Coverage**: 123 automated test cases passing cleanly with zero failures or errors.
- [x] **Frontend Production Build**: Clean TypeScript compilation and Vite bundling with zero errors.
- [x] **Secrets Hygiene**: `.gitignore` configured to exclude `.env`, virtual environments, and build artifacts. Template `.env.example` provided.

### Pending Deliverables Required for Submission:
To complete final assessment submission, the following external actions must be performed:
1. **Git Repository Publication**:
   - The local Git repository has been initialized (`git init`), and all sensitive files are verified excluded.
   - Outstanding action: Add a remote GitHub/GitLab repository origin (`git remote add origin <URL>`), commit the project files, and push to the remote repository.
2. **Production Deployment**:
   - The application has not been deployed to a live cloud host (e.g., Render, Railway, AWS, DigitalOcean).
   - Outstanding action: Provision a managed MySQL database and containerized backend/frontend web services with production environment variables (`DEBUG=False`).
3. **Safe Demo Access**:
   - No public production URL or live evaluator credentials currently exist.
   - Outstanding action: If an interactive live demo is required by the evaluator, seed non-production sample accounts and provide demo credentials in the submission portal.
