# Advanced Layout Patterns

Reference for complex diagram layouts. Consult when building diagrams with double rows,
deeply nested containers, multi-tenant boundaries, or complex splits.

## Height Reference

Each element type occupies a fixed pixel height:

| Element | Height | Notes |
|---------|--------|-------|
| Title bar | 50px + 10px gap | Only if `title` is set |
| Subtitle | 22px | Only if `subtitle` is set |
| Layer (1-6 services) | 95px + 8px gap | Single row of icons |
| Layer (7+ services) | 165px + 8px gap | Auto-splits into two sub-rows |
| Arrow | 28px | Includes arrowhead |
| Bridge | 60px | Bidirectional arrow + label |
| Legend | 30px | Color swatch bar |
| Container | 32px label + children + 10px pad + 8px gap | Recursive |
| Split | max(column heights) + 8px gap | Columns render side-by-side |

## Double Row (7+ Services)

When a layer has more than 6 services, the renderer automatically splits them into
two sub-rows. The first row gets `ceil(n/2)` items, the second gets the rest.

```json
{"type": "layer", "label": "VERTEX AI AGENT ENGINE", "color": "blue", "services": [
  {"icon": "agents", "label": "Agent Engine", "sublabel": "Runtime"},
  {"icon": "developer-tools", "label": "ADK Framework", "sublabel": "Dev Kit"},
  {"icon": "databases", "label": "Sessions", "sublabel": "Memory"},
  {"icon": "vertex-ai", "label": "Vertex AI Eval", "sublabel": "Evaluation"},
  {"icon": "observability", "label": "Logging", "sublabel": "Monitoring"},
  {"icon": "ai-machine-learning", "label": "Search Grounding", "sublabel": "RAG"},
  {"icon": "security-identity", "label": "Model Armor", "sublabel": "I/O Safety"}
]}
```

This renders as two rows: 4 icons on top, 3 on bottom, inside a 165px tall container.

## Nested Containers

Containers can nest inside containers for boundaries like Project > VPC > Subnet.
Keep nesting to 2 levels maximum for readability.

```json
{"type": "container", "label": "GCP PROJECT", "color": "green", "elements": [
  {"type": "container", "label": "VPC NETWORK", "color": "blue", "elements": [
    {"type": "layer", "label": "COMPUTE", "color": "blue", "services": [...]},
    {"type": "arrow", "color": "purple"},
    {"type": "layer", "label": "DATA", "color": "purple", "services": [...]}
  ]},
  {"type": "arrow", "color": "gray"},
  {"type": "layer", "label": "INFRASTRUCTURE", "color": "gray", "services": [
    {"icon": "security-identity", "label": "IAM"},
    {"icon": "observability", "label": "Cloud Logging"},
    {"icon": "operations", "label": "Monitoring"}
  ]}
]}
```

## Multi-Tenant with Legend

For architectures with distinct tenants, use containers for each tenant,
a bridge between them, and a legend at the top.

```json
{
  "title": "AI Agent Platform",
  "elements": [
    {"type": "legend", "items": [
      {"color": "green", "label": "Customer"},
      {"color": "blue", "label": "Platform"},
      {"color": "purple", "label": "AI / ML"},
      {"color": "gray", "label": "Infrastructure"}
    ]},
    {"type": "container", "label": "CUSTOMER TENANT", "color": "green", "elements": [
      ...layers...
    ]},
    {"type": "bridge", "label": "A2A Protocol", "color": "red"},
    {"type": "container", "label": "PLATFORM TENANT", "color": "blue", "elements": [
      ...layers...
    ]}
  ]
}
```

## Split with Containers

Splits can contain containers (not just layers) for complex side-by-side layouts.

```json
{"type": "split", "ratios": [2, 1], "elements": [
  {"type": "container", "label": "PRIMARY", "color": "blue", "elements": [
    {"type": "layer", "label": "SERVICES", "color": "blue", "services": [...]}
  ]},
  {"type": "container", "label": "SECONDARY", "color": "gray", "elements": [
    {"type": "layer", "label": "CACHE", "color": "gray", "services": [...]}
  ]}
]}
```

## Design Principles

1. **Limit colors to 4-5** per diagram
2. **Reserve green** for the outermost boundary (project/tenant)
3. **Use red/orange** for input/ingestion layers
4. **Use blue** for compute/processing
5. **Use purple** for data/AI layers
6. **Use gray** for infrastructure/cross-cutting concerns
7. **Keep layers to 3-6 icons** — 7+ auto-splits but can look crowded
8. **Place legend first** in elements for top positioning
9. **Use bridges** only between major boundaries (tenants, systems)
10. **Use arrows** between layers within the same boundary
