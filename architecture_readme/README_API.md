# Take-Home Assignment Backend

A FastAPI backend scaffold built for the backend developer
take-home assignment. The current implementation includes
the API, persistence, authentication, audit, and
webhook/message-processing foundations.

The webhook-specific architecture and message lifecycle
are documented separately in `architecture_readme/README_WEBHOOK.md`.

## Current Architecture

``` text
Client
  │
  ▼
FastAPI Routers
  │
  ├── Request/response schemas
  ├── Authentication dependencies
  │
  ▼
Service Layer
  │
  ├── Entity-specific business logic
  ├── Validation
  ├── Audit coordination
  │
  ▼
BaseService
  │
  └── Generic persistence operations
  │
  ▼
Async SQLAlchemy / SQLModel
  │
  ▼
PostgreSQL
```

The application follows a layered structure. Routers handle HTTP
concerns, services contain business logic, and database persistence is
performed through asynchronous SQLAlchemy sessions using SQLModel
models.

## Technology Stack

-   **FastAPI** --- API framework
-   **SQLModel** --- ORM models and database mapping
-   **SQLAlchemy AsyncSession** --- asynchronous database access
-   **PostgreSQL** --- relational database
-   **Alembic** --- schema migrations
-   **PyJWT** --- JWT generation and decoding
-   **Passlib + bcrypt** --- password hashing
-   **Redis** --- JWT blacklist storage for logout
-   **Pydantic Settings** --- application/security configuration
-   **uv** --- Python dependency and environment management

## Application Layers

### API / Routers

Routers expose HTTP endpoints and inject dependencies such as
database-backed services and the authenticated user.

The router is intentionally kept thin. For example, an authenticated
campaign creation request follows:

``` text
POST /campaign/
      │
      ├── CampaignCreate
      ├── UserAuthDep
      └── CampaignServiceDep
                │
                ▼
        CampaignService.create_campaign(...)
```

Campaign read operations are public. Campaign create, update, and delete
operations require an authenticated user.

### Dependency Injection

FastAPI dependencies are defined using `Annotated` aliases. These
provide reusable database sessions, services, and authentication
dependencies without manually constructing them inside endpoints.

Conceptually:

``` python
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CampaignServiceDep = Annotated[CampaignService, Depends(get_campaign_service)]
UserAuthDep = Annotated[User, Depends(get_current_user)]
```

### Service Layer

Entity-specific services contain validation and business rules.

`CampaignService`, for example, is responsible for:

-   Creating campaigns
-   Fetching campaigns
-   Updating campaigns
-   Deleting campaigns
-   Validating campaign-specific conditions
-   Creating audit records for mutations

Generic database operations live in `BaseService` rather than being
repeated in each entity service.

``` text
CampaignService
      │
      └── BaseService
              ├── _get(...)
              ├── _get_all(...)
              ├── _create(...)
              ├── _update(...)
              └── _delete(...)
```

The ORM entity passed to a generic persistence method determines the
mapped PostgreSQL table.

## Database Models

The current domain includes:

``` text
Cohort
Campaign
Teacher
Message
MessageEvent
User
AuditEvent
```

SQLModel metadata is used by Alembic to detect schema changes and
generate migrations.

### Campaign

A campaign currently contains information such as:

-   ID
-   Name
-   Description
-   Status
-   Status remark
-   Creation timestamp

Campaign status is represented using a PostgreSQL-backed enum.

### User

`User` provides the current authentication identity and contains:

-   ID
-   Name
-   Email
-   Email verification state
-   Active state
-   Password hash
-   Creation timestamp

Passwords are never stored directly. Registration accepts a plain-text
password, which is hashed before the `User` record is persisted.

### AuditEvent

`AuditEvent` is a generic audit model rather than a Campaign-specific
history table.

Important fields include:

``` text
entity_type
entity_id
action
actor_id
changes
event_metadata
created_at
```

`entity_id` is deliberately not a foreign key to a particular domain
table. This allows the same audit structure to support different entity
types and allows audit history to survive deletion of the original
entity.

`actor_id` references the authenticated `User`.

For example, a campaign update can record:

``` json
{
  "status": {
    "from": "Planned",
    "to": "Ongoing"
  }
}
```

Campaign create, update, and delete operations currently produce audit
events.

`MessageEvent` is separate from `AuditEvent`: it represents
message-domain events rather than generic application auditing.

## Authentication

Authentication uses JWT bearer tokens.

``` text
Register
   │
   ▼
Password hashed
   │
   ▼
User stored
   │
   ▼
Login
   │
   ├── Verify email/password
   │
   ▼
JWT issued
   │
   ▼
Authenticated API request
```
> **Note:** `User` includes `email_verified` and `is_active` fields for a potential account verification and activation flow. These fields are not currently used by the authentication flow. Email verification and account activation are intentionally outside the scope of this application.

Each JWT contains a unique `jti` (JWT ID), an expiry, and information
required to identify the user.

Protected endpoints resolve the token through a FastAPI authentication
dependency and load the corresponding user.

## Logout and Token Blacklisting

JWTs are stateless and cannot simply be destroyed by the server after
being issued. Logout therefore blacklists the token's unique `jti`.

``` text
JWT
 │
 ▼
Decode token
 │
 ▼
Read jti
 │
 ▼
Store jti in Redis blacklist
 │
 ▼
JWT is rejected until it expires
```
The Redis blacklist entry uses the JWT's remaining lifetime as
its TTL, so the `jti` is automatically removed once the token
itself has expired.

A newly issued token receives a different `jti` and can be used
normally.

## Audit Flow

Campaign mutations use the authenticated user as the audit actor.

``` text
Authenticated User
        │
        ▼
Campaign mutation
        │
        ├──────────────► Campaign
        │
        └──────────────► AuditEvent
                           │
                           ├── entity_type = "campaign"
                           ├── entity_id = campaign.id
                           ├── actor_id = user.id
                           ├── action
                           └── changes
```

For updates, the service captures the previous values before applying
`sqlmodel_update()` so that both the old and new state can be recorded.

## Database Migrations

Database schema changes are managed exclusively through Alembic.

The application does not create tables at startup with `create_all()`.
Model changes should instead follow:

``` text
Modify SQLModel
      │
      ▼
Generate Alembic revision
      │
      ▼
Review migration
      │
      ▼
Apply migration
```

This keeps database evolution explicit and reproducible.

## Current API Scope

The API currently supports:

-   User registration
-   User login
-   JWT authentication
-   User logout through token blacklisting
-   Public Campaign reads
-   Authenticated Campaign creation
-   Authenticated Campaign updates
-   Authenticated Campaign deletion
-   Authenticated Teacher creation
-   Campaign audit history generation
-   Health check
-   Incoming message webhook
-   Message status webhook
-   Shared-secret webhook authentication
-   Message event persistence

The API and webhook flows operate as two HTTP-facing parts of
the same application. The regular API handles user-driven
operations such as authentication and campaign management,
while the webhook endpoints handle simulated messaging-provider events.

Both parts share the same database, service, dependency, and
configuration infrastructure.
