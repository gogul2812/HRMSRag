# Shared UI

**Technology:** TypeScript, React 18, design tokens

## Purpose

`@rag-platform/shared-ui` is shared by Admin Portal and User Portal:

- Design tokens (colours, typography)
- `Button`, `StatusBadge`, `DocumentUploadZone`
- `ChatBubble`, `CitationChip`
- `createApiClient` — JWT-aware fetch wrapper
- `useChatStream` — SSE token stream helper

## Usage

```ts
import {
  Button,
  ChatBubble,
  createApiClient,
  useChatStream,
} from "@rag-platform/shared-ui";
```
