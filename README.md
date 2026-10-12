# StockPilot — Multi-Tenant Inventory & Sales Order Management System

StockPilot is an enterprise-grade, multi-tenant inventory and sales order management platform engineered with a **Django REST Framework (DRF)** backend, a **React 19 + TypeScript + Vite** frontend, and a **MySQL-compatible TiDB Cloud Serverless** relational database.

The platform provides strict tenant isolation, server-authoritative pricing, atomic database transactions with concurrency row-locking, append-only inventory movement audit logs, and fine-grained role-based access control (Workspace Owner vs. Staff).

---

## Live Deployment & Repository Links

- **GitHub Repository**: [https://github.com/Mohinkhan48/StockPilot](https://github.com/Mohinkhan48/StockPilot)
- **Live Frontend Application**: [https://stockpilot-mohin-app.netlify.app](https://stockpilot-mohin-app.netlify.app/)
- **Live Backend API**: [https://stockpilot-49vs.onrender.com](https://stockpilot-49vs.onrender.com/)
- **Database Engine**: [TiDB Cloud Serverless](https://tidbcloud.com/) (MySQL 8 wire-compatible, distributed SQL)

---

## Table of Contents

- [Evaluator Access & Self-Registration Guide](#evaluator-access--self-registration-guide)
- [Project Overview & Core Capabilities](#project-overview--core-capabilities)
- [Architecture & Tech Stack](#architecture--tech-stack)
- [Database Schema & Data Relationships](#database-schema--data-relationships)
- [Multi-Tenant Workspace Isolation](#multi-tenant-workspace-isolation)
- [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
- [Inventory Transaction Strategy & Concurrency](#inventory-transaction-strategy--concurrency)
- [Multi-Item Order Lifecycle & Pricing Integrity](#multi-item-order-lifecycle--pricing-integrity)
- [Dashboard Metrics & Real-Time Aggregations](#dashboard-metrics--real-time-aggregations)
- [API Endpoints Reference](#api-endpoints-reference)
- [Environment Variables & Configuration](#environment-variables--configuration)
- [Database Migrations & TiDB Compatibility Notes](#database-migrations--tidb-compatibility-notes)
- [Local Setup & Installation Instructions](#local-setup--installation-instructions)
- [Automated Test Suites & Verification](#automated-test-suites--verification)
- [Production Deployment Architecture](#production-deployment-architecture)
- [Known Limitations & Outstanding Issues](#known-limitations--outstanding-issues)
- [AI Assistance Disclosure](#ai-assistance-disclosure)

---

## Evaluator Access & Self-Registration Guide

Assessors can immediately evaluate the full end-to-end functionality of StockPilot on the live production deployment without requiring pre-shared credentials.

### Step-by-Step Evaluation Walkthrough:

1. **Access the Application**:
   - Open the live frontend at [https://stockpilot-mohin-app.netlify.app](https://stockpilot-mohin-app.netlify.app/).
   - The root URL (`/`) presents the clean login portal.

2. **Self-Registration**:
   - Click **"Create account"** or navigate directly to `/register`.
   - Complete the registration form with a unique username, email, and password.
   - Upon registration, an authentication token is issued, and you are directed to the **Workspaces** dashboard.

3. **Workspace Provisioning**:
   - Click **"Create Workspace"** and assign a name (e.g., *Apex Logistics* or *Acme Retail*).
   - The creating user is automatically assigned the **Owner** role for that workspace.

4. **Product Catalog & Inventory Audit**:
   - Navigate to **Products** and add catalog items with starting stock, prices, and low-stock alert thresholds.
   - Test the **Restock** modal to increase inventory with optional audit notes.
   - Test the **Adjust Stock** modal to perform manual balance corrections (mandatory reason required).
   - Open **Audit Movements** to view the append-only ledger tracking every stock transition with before/after quantities and user attribution.

5. **Multi-Item Sales Order Lifecycle**:
   - Navigate to **Orders** and click **"New Order"**.
   - Add multiple items. In **Pending** status, notice that live product prices calculate an *estimated total*, but **no stock is deducted** and line prices remain unfrozen.
   - Click **"Confirm Order"**. The server acquires row-level locks, verifies stock availability across all line items, atomically deducts quantities, stamps permanent historical price snapshots, and logs `sale` audit records.
   - Test order fulfillment by transitioning from **Confirmed** to **Completed**.
   - Create a second order and test **Cancel Order**: notice that cancelling a confirmed order atomically restores inventory levels and logs `return` audit records.

6. **Role-Based Access Testing (Owner vs. Staff)**:
   - Register a second user account (e.g., in an incognito window).
   - In your primary Owner workspace, navigate to **Members**, invite the second user by username, and assign the **Staff** role.
   - Log in as the Staff user: verify that Staff can create products, restock items, and confirm orders, but are blocked with `403 Forbidden` if attempting to delete products, delete pending orders, or alter workspace settings.

---

## Project Overview & Core Capabilities

StockPilot solves the critical data integrity, concurrency, and multi-tenancy challenges inherent in inventory and order fulfillment systems:

1. **Strict Multi-Tenant Scoping**: Complete database and view-layer isolation ensuring that workspace data is never cross-accessible or enumerable.
2. **Atomic Concurrency Control**: High-volume order confirmations lock product rows in consistent ascending primary-key order (`SELECT ... FOR UPDATE`), eliminating deadlocks and overselling race conditions.
3. **Server-Authoritative Pricing**: Clients never dictate line item prices or order totals. Historical prices are stamped only upon confirmation, insulating historical accounting from subsequent product catalog modifications.
4. **Append-Only Movement Ledger**: Every inventory alteration (restock, sale, manual adjustment, cancellation return) writes an immutable `InventoryMovement` log entry that can never be modified or deleted.
5. **Real-Time SQL Aggregations**: Dashboard metrics are computed in single server-side aggregate database queries rather than deriving statistics client-side from paginated sets.

---

## Architecture & Tech Stack

```
┌─────────────────────────────────────────────────────────────┐
│                       Client Browser                        │
│             React 19 + TypeScript + Vite SPA                │
│             Hosted on Netlify (CDN Edge)                    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS (REST / Auth Token)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Django REST Framework API                   │
│          Gunicorn WSGI + WhiteNoise Static Assets           │
│             Hosted on Render Web Service                    │
└──────────────────────────────┬──────────────────────────────┘
                               │ MySQL 8 Protocol (TLS/SSL)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 TiDB Cloud Serverless                       │
│        Distributed MySQL-Compatible SQL Database            │
└─────────────────────────────────────────────────────────────┘
```

### Backend Services
- **Framework**: Django 5.2.18
- **REST Engine**: Django REST Framework (DRF) 3.18.3
- **WSGI Application Server**: Gunicorn 23.0.0
- **Static Assets**: WhiteNoise 6.8.2
- **Authentication**: TokenAuthentication (`rest_framework.authtoken`) with session backup
- **CORS Management**: `django-cors-headers` 4.9.0
- **Database Adapters**: `mysqlclient` 2.3.0 (native C client) with `PyMySQL` 1.1.1 fallback and `cryptography` 44.0.0

### Frontend Application
- **Framework**: React 19.2.8
- **Build Tool**: Vite 8.3.4 (with `@vitejs/plugin-react`)
- **Language**: TypeScript ~6.0.2 (strict typing enforced)
- **Routing**: React Router DOM 7.18.4
- **HTTP Client**: Axios 1.20.0 (interceptor-based token injection)
- **UI & Icons**: Lucide React 1.55.0
- **Styling**: Handcrafted CSS design system with CSS custom properties (dark/light contrast, glassmorphism, responsive data grids)
- **Test Runner**: Vitest 5.0.4

### Database Engine
- **Provider**: TiDB Cloud Serverless (Distributed MySQL 8 wire-compatible)
- **Collation**: `utf8mb4` with `utf8mb4_unicode_ci`
- **Port**: 4000 (TLS/SSL enforced)

---

## Database Schema & Data Relationships

The entity model is designed with relational integrity, composite uniqueness constraints, and foreign key protection:

```mermaid
erDiagram
    User ||--o{ WorkspaceMembership : "holds"
    Workspace ||--o{ WorkspaceMembership : "has"
    User ||--o{ Workspace : "owns"
    Workspace ||--o{ Product : "contains"
    Workspace ||--o{ Order : "scopes"
    Product ||--o{ OrderItem : "referenced by"
    Order ||--o{ OrderItem : "contains"
    Product ||--o{ InventoryMovement : "tracks"
    Order ||--o{ InventoryMovement : "originates"
    User ||--o{ InventoryMovement : "performed by"
    User ||--o{ Order : "created by"

    Workspace {
        int id PK
        string name
        int owner_id FK
        datetime created_at
    }

    WorkspaceMembership {
        int id PK
        int workspace_id FK
        int user_id FK
        string role "owner | staff"
        datetime joined_at
    }

    Product {
        int id PK
        int workspace_id FK
        string name
        string sku "unique per workspace"
        decimal price "declared CHECK >= 0"
        int stock_quantity "declared CHECK >= 0"
        int low_stock_threshold "declared CHECK >= 0"
        boolean is_active
        datetime created_at
    }

    Order {
        int id PK
        int workspace_id FK
        int created_by_id FK
        string status "pending | confirmed | completed | cancelled"
        text notes
        datetime created_at
    }

    OrderItem {
        int id PK
        int order_id FK
        int product_id FK "PROTECT"
        int quantity "declared CHECK >= 1"
        string product_name "snapshot"
        string product_sku "snapshot"
        decimal unit_price "snapshot, declared CHECK >= 0"
    }

    InventoryMovement {
        int id PK
        int product_id FK
        int order_id FK "nullable"
        string movement_type "restock | sale | adjustment | return"
        int quantity "signed integer"
        int resulting_stock "snapshot"
        int created_by_id FK
        datetime created_at "immutable"
    }
```

### Relational Integrity Rules:
1. **Workspace Scoping**: Every `Product` and `Order` belongs to exactly one `Workspace`.
2. **Product SKU Uniqueness**: Enforced via composite constraint `UniqueConstraint(fields=['workspace', 'sku'])`. The same SKU can exist in different workspaces without collision.
3. **Protected History**: `OrderItem.product` uses `on_delete=models.PROTECT`, preventing product deletions from corrupting historical sales records.
4. **Owner Protection**: `Workspace.owner` uses `on_delete=models.PROTECT`, preventing deletion of user accounts that actively own workspaces.
5. **Cascading Tenant Teardown**: Deleting a workspace cascades cleanly to all contained products, orders, memberships, and audit records.

---

## Multi-Tenant Workspace Isolation

StockPilot implements multi-tenancy at both the routing and database query layers:

- **Explicit URL Path Scoping**: All workspace resources reside under `/api/workspaces/<workspace_id>/`.
- **Queryset Boundary Enforcement**: API views extend `WorkspaceContextMixin`, which retrieves the requested workspace, validates that `request.user` possesses an active `WorkspaceMembership`, and attaches `self.workspace` to the view instance.
- **Anti-Enumeration Security**: If an authenticated user queries a workspace ID they do not belong to, the API returns **`404 Not Found`** instead of `403 Forbidden`. This prevents malicious users from determining whether a specific tenant ID exists.
- **Cross-Workspace Item Injection Prevention**: When creating order lines, the serializer verifies that all submitted `product_id`s belong to the active workspace. Cross-workspace product references are rejected with HTTP 400 validation errors.
- **Object Resolution Scoping**: Detail routes (`/products/<pk>/`, `/orders/<pk>/`) filter simultaneously by both `pk` and `workspace=self.workspace`. Supplying a valid ID from a foreign workspace returns `404 Not Found`.

---

## Role-Based Access Control (RBAC)

Each workspace member holds either the **Owner** or **Staff** role, governed by `accounts.permissions`:

| Capability | Workspace Owner | Workspace Staff | Non-Member / Outsider |
|---|:---:|:---:|:---:|
| View products, stock levels, & audit trail | Yes | Yes | 404 Not Found |
| Restock products & submit manual stock adjustments | Yes | Yes | 404 Not Found |
| Create sales orders & confirm / complete / cancel orders | Yes | Yes | 404 Not Found |
| View workspace aggregate metrics & low-stock alerts | Yes | Yes | 404 Not Found |
| Create new products in catalogue | Yes | Yes | 404 Not Found |
| Edit product metadata (name, price, threshold, active state) | Yes | Yes | 404 Not Found |
| Delete products from catalogue | **Yes** | **No (403 Forbidden)** | 404 Not Found |
| Delete draft (`pending`) orders | **Yes** | **No (403 Forbidden)** | 404 Not Found |
| Add new workspace members or remove staff | **Yes** | **No (403 Forbidden)** | 404 Not Found |
| Update workspace metadata or delete workspace | **Yes** | **No (403 Forbidden)** | 404 Not Found |

> **Note**: Primary workspace owners cannot be removed from their own workspace, preventing orphaned tenant accounts.

---

## Inventory Transaction Strategy & Concurrency

StockPilot guarantees mathematical and transactional consistency under high-volume concurrent operations:

### 1. Deterministic Row-Level Locking (`select_for_update`)
During order confirmations, cancellations, restocks, and manual adjustments, product rows are locked using database row-level locking. To eliminate database deadlocks between concurrent requests processing multiple items in varying orders, products are **always sorted and locked in deterministic ascending primary-key order**:

```python
# Acquire row locks in deterministic ascending PK order to prevent deadlocks:
for item in self.items.select_related('product').order_by('product_id'):
    product = Product.objects.select_for_update().get(pk=item.product_id)
```

### 2. All-or-Nothing Multi-Item Atomicity
Order confirmation executes inside `@transaction.atomic`. Before mutating any inventory, the system validates stock availability across **all items** in the order. If even a single item has insufficient stock:
- `InsufficientStockError` is raised.
- The transaction completely rolls back.
- Zero stock quantities are modified.
- No partial `sale` audit logs are written.
- The order remains safely in `pending` status.

### 3. Application Validation & Schema Check Constraints

StockPilot establishes defense-in-depth across the application and database schema layers:

- **Application-Level Enforcement (Django Layer)**:
  - Input validation is enforced on all API requests before database queries execute.
  - Product restocking requires a positive integer (`quantity > 0`).
  - Manual stock adjustments require a non-empty reason and verify that `current_stock + quantity >= 0`, raising `InsufficientStockError` on potential negative balances.
  - Order line items require `quantity >= 1`.
  - Multi-item order confirmations check real-time stock across all items before deducting inventory inside an atomic transaction.
- **Schema-Level Check Constraints (Model Declarations)**:
  - Django models and migrations declare SQL check constraints:
    - `product_stock_nonneg`: `stock_quantity >= 0`
    - `product_price_nonneg`: `price >= 0`
    - `product_low_stock_threshold_nonneg`: `low_stock_threshold >= 0`
    - `orderitem_qty_positive`: `quantity >= 1`
    - `orderitem_price_nonneg`: `unit_price >= 0` (evaluated when stamped)
  - **Database Engine Differences**: In standard MySQL 8.0.16+, check constraints are enforced directly by the database engine. In distributed MySQL-compatible engines such as TiDB, CHECK constraint enforcement varies based on server version and cluster configuration. StockPilot does not rely on TiDB engine-level check constraint enforcement; all boundary conditions, non-negativity rules, and integrity invariants are strictly validated and guaranteed at the Django application and transaction layer.

### 4. Append-Only Audit Ledger
The `InventoryMovement` model records every inventory modification with:
- `movement_type`: `restock`, `sale`, `adjustment`, or `return`.
- `quantity`: Signed integer (+ for stock additions, - for deductions).
- `resulting_stock`: Absolute snapshot of `Product.stock_quantity` immediately after the transaction commits.
- `created_by`: Foreign key attributing the action to the initiating user.
- `created_at`: Immutable UTC timestamp.

> **Immutability Guarantee**: Any invocation of `.save()` on an existing `InventoryMovement` record raises a Python `ValueError`, prohibiting edits or retrofits to the audit trail.

---

## Multi-Item Order Lifecycle & Pricing Integrity

An Order progresses through a strictly defined state machine:

```
[ PENDING ] ────── confirm() ──────► [ CONFIRMED ] ────── complete() ──────► [ COMPLETED ]
     │                                     │
     └─────────── cancel() ─────────┬──────┘
                                    ▼
                              [ CANCELLED ]
```

### Order States:

1. **Pending (Draft)**:
   - Line items and quantities are established.
   - **No stock is held or deducted**.
   - `OrderItem.unit_price`, `product_name`, and `product_sku` remain unset (`NULL`).
   - Line totals and order totals are calculated dynamically using the current live product prices (`estimated_total`).
   - The UI clearly indicates: *"Prices lock upon confirmation"*.

2. **Confirmed (Active)**:
   - Evaluates stock availability across all line items.
   - Atomically deducts stock from inventory and appends `sale` movements.
   - Stamps permanent, immutable snapshots onto `OrderItem` (`unit_price = product.price`, `product_name = product.name`, `product_sku = product.sku`).
   - If products are later repriced, renamed, or marked inactive, confirmed orders retain their exact historical figures.

3. **Completed (Fulfilled)**:
   - Terminal state indicating fulfillment. No stock adjustments take place because goods were already dispatched upon confirmation.

4. **Cancelled (Aborted)**:
   - **From Pending**: Status transitions to `cancelled`. No stock changes occur.
   - **From Confirmed**: Stock for each line item is restored atomically, and `return` audit entries are appended to the ledger.
   - **Cancellation Idempotency**: Calling `.cancel()` on an already cancelled order raises `InvalidTransitionError` immediately, preventing duplicate stock replenishment.

---

## Dashboard Metrics & Real-Time Aggregations

Workspace inventory statistics are served via `/api/workspaces/<id>/inventory/stats/` using a single server-side SQL aggregation query across the entire active catalog:

```python
stats = self.workspace.products.aggregate(
    total_products=Count('id'),
    total_active_products=Count('id', filter=Q(is_active=True)),
    total_stock_units=Coalesce(Sum('stock_quantity', filter=Q(is_active=True)), 0),
    low_stock_count=Count(
        'id',
        filter=Q(is_active=True, stock_quantity__lte=F('low_stock_threshold')),
    ),
)
```

This guarantees accurate metrics across products without client-side pagination bias or N+1 query overhead.

---

## API Endpoints Reference

All application endpoints are prefixed with `/api/`. Requests without authentication headers return `401 Unauthorized`. Requests accessing resources outside the user's workspace return `404 Not Found`.

### Authentication Endpoints (`/api/auth/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/auth/register/` | Public | Register new user account; returns auth token & user profile |
| `POST` | `/api/auth/login/` | Public | Authenticate with credentials; returns auth token |
| `POST` | `/api/auth/logout/` | Authenticated | Revoke and delete user auth token |
| `GET` | `/api/auth/me/` | Authenticated | Retrieve user profile and associated workspaces |

### Workspace Endpoints (`/api/workspaces/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/api/workspaces/` | Authenticated | List all workspaces the user belongs to |
| `POST` | `/api/workspaces/` | Authenticated | Create workspace (creator automatically assigned Owner) |
| `GET` | `/api/workspaces/<id>/` | Member | Retrieve workspace details |
| `PUT`/`PATCH` | `/api/workspaces/<id>/` | Owner | Update workspace metadata |
| `DELETE` | `/api/workspaces/<id>/` | Owner | Delete workspace and all scoped data |
| `GET` | `/api/workspaces/<id>/members/` | Member | List members and roles in workspace |
| `POST` | `/api/workspaces/<id>/members/` | Owner | Add existing user to workspace as Staff or Owner |
| `DELETE` | `/api/workspaces/<id>/members/<user_id>/` | Owner | Remove member from workspace (primary owner protected) |

### Products & Inventory Endpoints (`/api/workspaces/<id>/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `.../products/` | Member | List products with pagination, search (`?search=`), and filters (`?is_active=`, `?low_stock=`) |
| `POST` | `.../products/` | Member | Create a new product in workspace |
| `GET` | `.../products/<pk>/` | Member | Retrieve product details |
| `PUT`/`PATCH` | `.../products/<pk>/` | Member | Update product attributes (name, price, threshold, is_active) |
| `DELETE` | `.../products/<pk>/` | Owner | Delete product (blocked if referenced in order history) |
| `GET` | `.../products/low-stock/` | Member | List products where `stock_quantity <= low_stock_threshold` |
| `POST` | `.../products/<pk>/restock/` | Member | Restock product (`{"quantity": N, "notes": "..."}`) |
| `POST` | `.../products/<pk>/adjust/` | Member | Adjust balance (`{"quantity": ±N, "notes": "mandatory"}`) |
| `GET` | `.../products/<pk>/movements/` | Member | Retrieve append-only movement trail for product |
| `GET` | `.../inventory/movements/` | Member | Retrieve workspace-wide audit logs with filters |
| `GET` | `.../inventory/stats/` | Member | Single SQL aggregate returning catalog and stock statistics |

### Orders Endpoints (`/api/workspaces/<id>/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `.../orders/` | Member | List orders with pagination, status filter (`?status=`), ordering |
| `POST` | `.../orders/` | Member | Create a draft `pending` multi-item order |
| `GET` | `.../orders/<pk>/` | Member | Retrieve order details with line items and snapshots |
| `DELETE` | `.../orders/<pk>/` | Owner | Delete draft `pending` order (confirmed orders must be cancelled) |
| `POST` | `.../orders/<pk>/confirm/` | Member | Confirm order: lock rows, deduct stock, write audit, stamp snapshots |
| `POST` | `.../orders/<pk>/complete/` | Member | Complete order (`confirmed` → `completed`) |
| `POST` | `.../orders/<pk>/cancel/` | Member | Cancel order: restores stock and logs return if previously confirmed |

---

## Environment Variables & Configuration

Configuration is managed via environment variables. Reference templates are provided in [`StockPilot/.env.example`](StockPilot/.env.example) and [`frontend/.env.example`](frontend/.env.example):

### Backend Configuration (`StockPilot/.env`)

```env
# --- Django Security ---
DJANGO_SECRET_KEY=replace-me-with-a-long-random-secret-key
DEBUG=False
ALLOWED_HOSTS=127.0.0.1,localhost,your-backend.onrender.com

# --- Database Connection (MySQL / TiDB Cloud) ---
# Option A: Discrete Connection Parameters
DB_NAME=stockpilot_app
DB_USER=replace-with-db-username
DB_PASSWORD=replace-with-db-password
DB_HOST=127.0.0.1
DB_PORT=3306

# Option B: Managed Database URL (e.g. TiDB Cloud / Aiven)
# DATABASE_URL=mysql://USER:PASSWORD@HOST:PORT/stockpilot_app

# Cloud MySQL SSL options (enforced on TiDB Cloud)
# DB_SSL_MODE=REQUIRED
# DB_SSL_CA=/etc/ssl/certs/ca-certificates.crt

# --- CORS & CSRF Origins ---
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,https://your-frontend.netlify.app
CSRF_TRUSTED_ORIGINS=http://localhost:5173,https://your-frontend.netlify.app,https://your-backend.onrender.com
```

### Frontend Configuration (`frontend/.env`)

```env
# Base URL of the Django backend API (must point to /api)
# Local development:
VITE_API_URL=http://127.0.0.1:8000/api

# Production example:
# VITE_API_URL=https://your-backend.onrender.com/api
```

> [!CAUTION]
> Real credentials must never be committed to source control. Root and subdirectory `.gitignore` files strictly exclude `.env`, `.venv/`, `dist/`, and `node_modules/`.

---

## Database Migrations & TiDB Compatibility Notes

StockPilot maintains a linear migration history that cleanly resolves circular foreign key relationships between orders and inventory movements:

1. **`accounts.0001_initial`**: Creates `Workspace` and `WorkspaceMembership` tables with composite uniqueness constraints.
2. **`inventory.0001_initial`**: Creates `Product` and `InventoryMovement` base models.
3. **`orders.0001_initial`**: Creates `Order` and `OrderItem` models.
4. **`inventory.0002_initial`**: Resolves the circular reference by linking `InventoryMovement.order` foreign key to `Order` and establishing per-workspace SKU uniqueness.
5. **`inventory.0003_product_product_stock_nonneg_and_more`**: Applies database-level non-negativity check constraints.

### TiDB Cloud Schema Migration Compatibility Fix

During initial deployments on TiDB Cloud Serverless, standard Django migrations can encounter **Error 1072: Key column doesn't exist**. This occurs because standard Django MySQL migrations attempt to combine `ADD COLUMN` and `ADD CONSTRAINT FOREIGN KEY` into a single multi-clause `ALTER TABLE` statement, which TiDB's distributed schema engine parses concurrently before the column definition is persisted.

**Implementation Fix**:
StockPilot implements an automatic runtime compatibility patch in [`StockPilot/config/__init__.py`](StockPilot/config/__init__.py). When a connection to TiDB is detected (via host name, server version string, or environment flag), Django's `DatabaseSchemaEditor` dynamically sets `sql_create_column_inline_fk = None`. This instructs Django to first execute the `ADD COLUMN` statement, and subsequently append the foreign key constraint as a separate `ALTER TABLE` statement, resolving the multi-clause limitation on TiDB Cloud while leaving standard MySQL behavior untouched.

---

## Local Setup & Installation Instructions

### Prerequisites
- **Python**: 3.11+
- **Node.js**: 18.x or 20.x (npm 9+)
- **MySQL Server**: 8.0+ running on port 3306 (or a remote TiDB Cloud cluster)

---

### Step 1: Backend Setup

1. Clone repository and navigate to the project directory:
   ```bash
   git clone https://github.com/Mohinkhan48/StockPilot.git
   cd StockPilot
   ```

2. Enter the backend directory:
   ```bash
   cd StockPilot
   ```

3. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # On Linux / macOS:
   source venv/bin/activate
   ```

4. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Create local database in MySQL (if running a local MySQL server):
   ```sql
   CREATE DATABASE stockpilot_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

6. Configure environment variables:
   ```bash
   # On Windows (PowerShell):
   Copy-Item .env.example .env
   # On Linux / macOS / Git Bash:
   cp .env.example .env
   ```
   Edit `.env` with your local database credentials and set `DEBUG=True`.

7. Run database migrations:
   ```bash
   python manage.py migrate
   ```

8. (Optional) Create a superuser for Django admin access:
   ```bash
   python manage.py createsuperuser
   ```

9. Start the Django development server:
   ```bash
   python manage.py runserver 127.0.0.1:8000
   ```
   The backend API will be listening at `http://127.0.0.1:8000/`.

---

### Step 2: Frontend Setup

1. In a separate terminal, navigate from the repository root to the `frontend/` directory:
   ```bash
   cd frontend
   ```
   *(Or if currently in the backend folder, run `cd ../frontend`)*

2. Install frontend dependencies:
   ```bash
   npm install
   ```

3. Configure frontend environment variables:
   ```bash
   # On Windows (PowerShell):
   Copy-Item .env.example .env
   # On Linux / macOS / Git Bash:
   cp .env.example .env
   ```
   Ensure `VITE_API_URL=http://127.0.0.1:8000/api`.

4. Start Vite development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:5173/` in your browser.

---

## Automated Test Suites & Verification

### Backend Test Suite (Django / DRF)
The backend test suite covers model constraints, atomic service methods, concurrency, workspace scoping, and role authorization.

To execute the backend test suite:
```powershell
cd StockPilot
python manage.py test --verbosity=2
```

**Previously Recorded Test Results**:
```text
Ran 123 tests in 159.345s
OK
Destroying test database for alias 'default' ('test_stockpilot_app')...
```

#### Key Test Coverage Areas:
- **Accounts & RBAC**: Token generation/revocation, member role checks, workspace owner immutability, cross-workspace 404 anti-enumeration.
- **Inventory Operations**: SKU uniqueness scoped to workspace, model validation, immutability of `InventoryMovement` records, negative stock prevention.
- **Order Lifecycle & Pricing**: Rejection of client-submitted unit prices, dynamic estimated totals for pending orders, atomic multi-item stock deductions, snapshot retention after product changes, cancellation idempotency.
- **Concurrency**: Deterministic row-locking verifying that concurrent order confirmation requests execute safely without overselling.

---

### Frontend Test Suite (Vitest)
The frontend includes unit and component tests executed with Vitest:

```bash
cd frontend
npm test
```

**Previously Recorded Test Results**:
```text
 ✓ src/components/orders/CancelOrderModal.test.tsx (9 tests) 21ms

 Test Files  1 passed (1)
      Tests  9 passed (9)
   Duration  403ms
```

### Frontend Type-Check & Production Bundle Build:
To verify TypeScript compilation and Vite bundling:
```bash
cd frontend
npm run build
```

**Previously Recorded Build Output**:
```text
> frontend@0.0.0 build
> tsc -b && vite build

vite v8.3.4 building client environment for production...
✓ 1992 modules transformed.
dist/index.html                   0.76 kB │ gzip:   0.44 kB
dist/assets/index-D6vD4u1K.css    6.08 kB │ gzip:   1.82 kB
dist/assets/index-BZbjfXjN.js   394.52 kB │ gzip: 117.04 kB
✓ built in 1.05s
```

---

## Production Deployment Architecture

The live production deployment of StockPilot is architected across three specialized cloud tiers:

```
┌─────────────────────────────────┐       HTTPS       ┌─────────────────────────────────┐
│          Netlify SPA            │ ────────────────► │       Render Web Service        │
│   (React 19 + TypeScript)       │    REST API       │   (Django DRF + Gunicorn WSGI)  │
│  stockpilot-mohin-app.netlify   │                   │   stockpilot-49vs.onrender.com  │
└─────────────────────────────────┘                   └────────────────┬────────────────┘
                                                                       │ TLS (TCP 4000)
                                                                       ▼
                                                      ┌─────────────────────────────────┐
                                                      │      TiDB Cloud Serverless      │
                                                      │   (Distributed MySQL Database)  │
                                                      └─────────────────────────────────┘
```

### 1. Database Tier: TiDB Cloud Serverless
- Provisioned a Serverless TiDB cluster (100% MySQL 8 wire-compatible).
- Database created with `utf8mb4` encoding and TLS encryption required.

### 2. Backend Tier: Render Web Service
- **Service Name**: `stockpilot-49vs`
- **Root Directory**: `StockPilot`
- **Build Command**: `./build.sh` (installs dependencies, collects WhiteNoise static files, applies migrations)
- **Start Command**: `gunicorn config.wsgi:application`
- **Environment Variables**:
  - `DJANGO_SECRET_KEY`: High-entropy random production secret.
  - `DEBUG`: `False`
  - `ALLOWED_HOSTS`: `localhost,127.0.0.1,stockpilot-49vs.onrender.com`
  - `DATABASE_URL`: `mysql://USER:PASSWORD@HOST:4000/stockpilot_app`
  - `DB_SSL_MODE`: `REQUIRED`
  - `CORS_ALLOWED_ORIGINS`: `https://stockpilot-mohin-app.netlify.app`
  - `CSRF_TRUSTED_ORIGINS`: `https://stockpilot-mohin-app.netlify.app,https://stockpilot-49vs.onrender.com`

### 3. Frontend Tier: Netlify SPA
- **Site Name**: `stockpilot-mohin-app`
- **Configuration Files**: [`netlify.toml`](netlify.toml) & [`frontend/netlify.toml`](frontend/netlify.toml)
- **Base Directory**: `frontend`
- **Publish Directory**: `dist`
- **Build Command**: `npm install && npm run build`
- **SPA Rewrites**: Redirects rule `/* -> /index.html 200` to support client-side React Router navigation.
- **Environment Variable**: `VITE_API_URL=https://stockpilot-49vs.onrender.com/api`

---

## Known Limitations & Outstanding Issues

The following items are documented transparently for evaluation:

1. **Chrome Safe Browsing Warning on Render Backend (Unresolved Deployment Issue)**:
   - A Google Chrome Safe Browsing warning (*"Deceptive site ahead"*) has been observed when navigating directly to the Render backend domain (`https://stockpilot-49vs.onrender.com/`).
   - **Status**: The warning has been observed and remains an active, unresolved deployment issue; its underlying cause has not been confirmed, and no claims regarding backend safety can be made without independent verification. Direct visits to the backend URL in Google Chrome may be blocked or flagged with this warning banner. Cross-origin API requests made from the live Netlify frontend interface (`https://stockpilot-mohin-app.netlify.app/`) to the backend API currently complete over HTTPS, but direct browser navigation to the backend domain remains affected until the issue is investigated and resolved.

2. **Render Free-Tier Spin-Down (Cold Starts)**:
   - The backend is hosted on Render's free tier, which puts inactive web services to sleep after 15 minutes of inactivity. An initial HTTP request after dormancy may take 30 to 50 seconds to warm up the Gunicorn process. Subsequent requests respond with standard low latency.

3. **Product Deletion vs. Catalog Archival**:
   - The platform prevents deleting products that are referenced by existing sales orders (`on_delete=models.PROTECT`). Attempting to delete such a product raises an error. The recommended workflow for discontinued items is to toggle `is_active=False` rather than deleting the catalog record.

---

## AI Assistance Disclosure

In alignment with evaluation and academic transparency standards:

- **AI Tools Utilized**: Google DeepMind Antigravity AI coding assistant powered by the Gemini model family.
- **Scope of AI Collaboration**:
  - Threat modeling and validation for multi-tenant isolation and 404 anti-enumeration protections.
  - Designing deterministic ascending primary-key row-locking (`select_for_update`) to prevent concurrency deadlocks and inventory overselling.
  - Implementing the server-authoritative pricing flow with deferred line item snapshots.
  - Formulating the TiDB schema migration compatibility patch in `StockPilot/config/__init__.py`.
  - Authoring and maintaining the 123 backend Django test cases and frontend Vitest suite.
  - Diagnosing deployment configurations across Render, Netlify, and TiDB Cloud.
- **Human Author Responsibility**: All business logic implementations, database constraints, architectural designs, code modifications, and test suite executions were verified, reviewed, and validated for full compliance.
