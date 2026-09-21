# Origin Hut

Origin Hut is being built from scratch as an export/import intelligence and trade operating platform.

## Platform principle

External data sources are not the product.

Origin Hut will normalize trade, market, company, compliance, logistics and transaction data into one internal model and expose useful business workflows through its own APIs.

## Initial architecture

### apps/web

Next.js frontend.

### apps/api

TypeScript/Fastify application API.

### services/data

Python ingestion and transformation services for external datasets and APIs.

### packages/shared

Shared application contracts and utilities.

### database

PostgreSQL schema migrations, seeds and reference datasets.

### infra

Local/Docker and Azure infrastructure definitions.

## Initial functional domains

- Product and HS classification
- Market intelligence
- Trade flows
- Buyers and suppliers
- Company verification
- Commodity intelligence
- RFQ and quotation
- Export costing
- Compliance
- Trade documents
- Deals
- Finance and risk
- Logistics and shipment status
- Alerts and intelligence

## Deployment lifecycle

Local development
→ local testing
→ Vercel preview
→ Azure production
→ originhut.com
