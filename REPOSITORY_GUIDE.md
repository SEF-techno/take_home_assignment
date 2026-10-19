# Repository Guide

This guide is intended to help you understand and navigate the
repository before beginning the assignment. It explains where the major
pieces live, why some architectural choices were made, and which parts
of the system are deliberately simulated or kept out of scope.

This is not intended to document every function. You are encouraged to
trace the implementation yourself and follow dependencies between
layers.

## 1. High-level structure

The `app/` directory contains the application logic:

``` text
app/
├── api/
├── core/
├── db/
├── services/
├── config.py
├── main.py
└── utils.py
```

Outside `app/`, you will also find Alembic migrations, scripts and seed
data, debugging utilities, and architecture documentation.

This is intentionally a small application. In a larger system, several
files and folders could reasonably be split further. Here, related
concerns are sometimes kept together where further separation would add
structure without adding much clarity.

## 2. `app/api/`

The `api/` package contains the HTTP-facing parts of the application,
including both regular API endpoints and webhook endpoints.

Webhooks could have been placed in a separate top-level module. However,
they are still HTTP endpoints exposed through FastAPI, and this
application is small enough that keeping them under the API layer avoids
unnecessary separation.

The package contains:

``` text
api/
├── routers/
├── schemas/
├── api_tag.py
├── dependencies.py
└── router.py
```

### Routers

`routers/` contains the route definitions.

Campaign routes expose operations for retrieving, creating, updating,
and deleting campaigns.

User routes contain authentication-related operations such as login and
logout. Login uses FastAPI's OAuth2 password flow and returns a JWT
access token. Logout blacklists the token so that it can no longer be
used.

Webhook routes expose the endpoints through which simulated provider
events enter the application.

Routers are intended to remain relatively thin. Business and persistence
logic is generally delegated to the service layer.

### Schemas

`schemas/` contains the Pydantic/API schemas used at the HTTP boundary.

For example, campaign schemas include representations for creating,
updating, and reading campaigns. They validate incoming data and
describe endpoint responses. The same pattern is used for users.

Webhook schemas describe the payload expected by the two webhook flows:

``` text
IncomingMessageWebhook
MessageStatusWebhook
```

### API tags and master router

`api_tag.py` defines tags used to group endpoints in the generated API
documentation.

`router.py` acts as the master API router. Individual routers are
included there, and the master router is included by the FastAPI
application.

### Dependencies

`dependencies.py` contains reusable FastAPI dependencies.

For example, a route that needs `CampaignService` does not need to
manually create a database session and instantiate the service:

``` text
Route
  ↓
CampaignService dependency
  ↓
Database session dependency
```

The file also contains authentication-related dependencies that can be
attached to protected routes.

At present, authentication establishes whether a user may access a
protected operation. The project does not implement ownership-based
campaign authorization. An authenticated user is therefore not
restricted to modifying only campaigns they personally created.

This is a deliberate scope boundary for the exercise, not an assumption
that this would always be sufficient in production.

## 3. `app/core/`

`core/` contains application-level concerns that are not specific to one
domain entity.

In this project, that includes security-related configuration such as
the OAuth2 password bearer setup.

What belongs in `core` is partly an architectural convention. The
current structure reflects the needs of this application rather than
prescribing a universal layout.

## 4. `app/db/`

The `db/` package contains database-related infrastructure.

### Models

The models file contains the SQLModel database models and the enums used
by them.

Because the application is small, these have deliberately been kept
together. A larger application could reasonably separate models by
domain and move enums into separate modules.

The domain includes entities such as `User`, `Campaign`, `Cohort`,
`Teacher`, `Message`, `MessageEvent`, and the audit-event model.

Read the models and their relationships carefully; they are one of the
most useful places to understand the domain.

### Database sessions

`session.py` configures the PostgreSQL connection and provides the
asynchronous database session used throughout the application.

### Redis

`redis.py` contains Redis-related functions used by authentication.

Redis is currently used for JWT blacklisting. When a user logs out, the
JWT identifier is added to the blacklist so that authentication can
reject the invalidated token.

## 5. `app/services/`

The service layer contains business and persistence logic.

Rather than placing database operations directly inside FastAPI routes,
entity-specific services encapsulate those operations.

For example:

``` text
Campaign route
      ↓
CampaignService
      ├── business checks
      └── database operations
```

There is also a shared base service containing common persistence
operations.

`WebhookService` contains the processing logic for incoming messages and
provider status events.

## 6. Configuration

`app/config.py` contains the application's settings classes.

Settings are grouped by concern, including application, database,
security, and webhook settings. Values are loaded from the environment
rather than embedded directly in application code.

This includes PostgreSQL, Redis, JWT/security, and webhook
configuration.

## 7. Application entry point and utilities

`app/main.py` creates the FastAPI application, registers the routers,
and exposes Scalar API documentation. The documentation can be used to
inspect and manually exercise the available endpoints.

`app/utils.py` contains shared utility functions, including JWT creation
and decoding using PyJWT.

## 8. Database migrations

Database schema changes are managed using Alembic.

The application does not rely on automatically creating its schema when
FastAPI starts. Changes to SQLModel definitions that affect the database
schema should therefore be considered alongside the corresponding
migration.

Reviewing the migration history may also help you understand how the
current schema evolved.

## 9. Scripts and seed data

The repository contains a `scripts/` directory with seed utilities. The
top-level seed script acts as an orchestrator for individual seed
functions.

Conceptually:

``` text
scripts/
├── seed.py
└── seeds/
    ├── cohort.py
    ├── teacher.py
    └── message.py
```

Not every entity has a CRUD API. The assignment adds authenticated teacher
creation, while cohorts and outbound messages still have no creation endpoint.

Seed data supplies enough state to exercise the implemented parts of the
system. This is particularly important for webhook testing.

A status webhook can only be processed if the application already knows
about the outbound message whose status the provider is reporting.
Because outbound message sending is not implemented in this scaffold, a
sample outbound message is seeded into the database.

This is an assignment/testing convenience, not the intended production
mechanism for sending messages.

Campaigns are created through the existing API rather than being part of
the same seed flow.

## 10. Understanding the webhook simulation

There is no real messaging provider connected to this repository.

The webhook implementation simulates the boundary that would normally
exist between this application and a provider such as a WhatsApp, SMS,
or Telegram integration.

### Incoming messages

In a real integration, the flow would broadly be:

``` text
Teacher
   ↓
Messaging provider
   ↓
Our webhook endpoint
   ↓
Provider-specific parsing / adaptation
   ↓
Application message processing
   ↓
Persistence
```

For this assignment, you can simulate the provider by sending the
expected webhook payload yourself. The required payload is described by
`IncomingMessageWebhook`.

The application identifies the teacher and persists the incoming
message.

### Outbound messages

The reverse direction is different. A production application would
normally initiate an outbound message by calling the messaging
provider's API:

``` text
Application / campaign logic
        ↓
Outbound messaging service
        ↓
Provider API
        ↓
Teacher
```

The provider would return or assign a provider-specific message
identifier. The application would retain that identifier so later
delivery events could be correlated with the correct internal message.

That outbound sending service is intentionally not implemented in this
scaffold.

Instead, the repository seeds an outbound message with a known provider
message ID. This gives you an existing message against which status
callbacks can be tested.

### Status callbacks

After accepting an outbound message, a provider may later call our
webhook with lifecycle events such as:

``` text
SENT
  ↓
DELIVERED
  ↓
READ
```

or a failure event.

The current status webhook simulates this behavior. Its expected payload
is represented by `MessageStatusWebhook`.

Status callbacks are persisted as `MessageEvent` records rather than
overwriting the message's event history. The implementation also
accounts for duplicate webhook delivery and events that arrive out of
chronological order.

For the reasoning behind these decisions, read the webhook architecture
README.

## 11. Webhook authentication

Webhook endpoints do not use the application's user JWT authentication.

A webhook represents an external provider calling the application, not a
logged-in user.

For this scaffold, webhook calls are protected using a shared secret
supplied through the `X-Webhook-Secret` header.

A production provider integration may use a different verification
mechanism, such as signed payloads or HMAC verification, depending on
the provider.

## 12. Authentication and authorization scope

The application implements user authentication, JWT-based access,
logout, and token blacklisting.

Do not assume that the existing authorization model represents a
complete production permissions system.

For example, campaign operations currently do not enforce creator
ownership, and tenant-level authorization has not been implemented.

These concerns were deliberately kept outside the initial scaffold.

When reviewing the system, distinguish between:

-   something intentionally outside the scope of this small application;
-   something that could reasonably be designed differently as the
    system grows; and
-   something that represents an actual correctness or engineering
    problem.

That distinction is important throughout the assignment.

## 13. Architecture documentation

The repository includes separate architecture documentation for the two
main perspectives of the application under `architecture_readme/`:

```text
architecture_readme/
├── README_API.md
└── README_WEBHOOK.md

The API README explains the regular application/API architecture.

The webhook README explains the message and event lifecycle, including
why outbound messages are seeded and how the simulated provider boundary
maps to a real integration.

The two parts share the same models, database infrastructure, services,
configuration, and FastAPI application.

Read both documents before making substantial changes.

## 14. Suggested way to explore the repository

You do not need to read the repository linearly.

A useful starting path is:

``` text
app/main.py
    ↓
app/api/router.py
    ↓
app/api/routers/
    ↓
app/api/dependencies.py
    ↓
app/services/
    ↓
app/db/models.py
```

For a specific endpoint, follow its route to its dependency, then into
the relevant service and database model.

For webhook behavior, also inspect:

``` text
app/api/schemas/webhook.py
        ↓
webhook routes
        ↓
WebhookService
        ↓
Message / MessageEvent
```

For authentication, follow the user routes through the authentication
dependencies, security configuration, JWT utilities, and Redis blacklist
functions.

Finally, inspect the seed scripts and the two architecture READMEs to
understand the parts of the system that are being simulated.

## Before you begin

The repository is intentionally a **small working scaffold**, not a
finished production application.

Some simplifications exist because they are sufficient for the exercise.
Some areas may warrant improvement. Some behavior may become problematic
under cases that are not immediately visible from the happy path.

Part of working with an existing backend is understanding which is
which.

Before making changes:

1.  Run the application and inspect the API documentation.
2.  Read the API and webhook architecture READMEs.
3.  Inspect the models and migrations.
4.  Run or inspect the seed process.
5.  Exercise the existing API and webhook flows.
6.  Trace relevant code paths through routes, dependencies, services,
    and persistence.

You should then have enough context to begin the assignment itself.
