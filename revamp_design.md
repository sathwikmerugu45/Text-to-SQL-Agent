# Design Document: SQLMind AI Platform

SQLMind is a next-generation, scalable Text-to-SQL platform designed to provide a premium, conversational experience for data exploration. Inspired by industry-leading AI interfaces like Gemini and Claude, SQLMind prioritizes ease of use, visual clarity, and multi-user collaboration.

## 1. Vision & Core Philosophy
The platform moves away from a single-page utility towards a holistic workspace. It treats data interaction as a conversation, where the SQL is a tool the AI uses to provide insights, not just the final output.

## 2. Key Frontend Features & Functionality

### 2.1 Workspace & Navigation
- **Persistent Sidebar**: A collapsible navigation bar housing:
    - **Chat History**: Grouped by date (Today, Yesterday, Last 30 Days).
    - **Data Sources**: Manage connected databases and schemas.
    - **Shared Workspaces**: For team collaboration on specific data projects.
    - **User Profile & Settings**: Management for API keys, billing (for scalability), and theme toggling.
- **New Chat Button**: Always accessible at the top of the sidebar.

### 2.2 Conversational Interface (The "Gemini" Experience)
- **Central Chat Window**: A clean, centered message stream.
- **Omnibox Input**: A floating or bottom-docked text area that supports multi-line queries, file uploads (CSV/Schema docs), and "Slash commands" (e.g., `/tables`, `/schema`).
- **AI Response Cards**:
    - **Natural Language Summary**: High-level insights at the top.
    - **Interactive Data Tables**: Paginated, searchable, and sortable results.
    - **Code Blocks**: Collapsible SQL with syntax highlighting and "Copy to Clipboard" functionality.
    - **Visualizations**: Automatic generation of relevant charts (Bar, Line, Pie) based on the result set.
    - **"Thinking" State**: A sophisticated animation showing the agent's step-by-step reasoning (Self-healing trace).

### 2.3 Advanced Tooling
- **Self-Healing Dashboard**: A dedicated view (or collapsible section) showing the "Retry" logic in action, visualizing how the agent corrected SQL syntax errors or schema mismatches.
- **Schema Explorer**: A visual representation of table relationships (ER Diagrams) to help users understand their data context.
- **Export Engine**: One-click export to CSV, Excel, PDF, or direct push to Google Sheets/BigQuery.

## 3. UI/UX & Styling Approach

### 3.1 Design Tokens (Catppuccin-inspired Professional Dark/Light)
- **Primary Color**: Deep Indigo or Electric Blue (`#3b82f6`) for actions.
- **Surface Colors**: Multi-layered grays/blacks to create depth (Glassmorphism effects for cards).
- **Typography**: Inter or San Francisco for a modern, clean, tech-focused feel.
- **Status Indicators**: Subtle glow effects for "Success", "Thinking", and "Self-Healing".

### 3.2 Layout Structure
- **Desktop**: Three-pane layout (Sidebar | Main Chat | Info/Schema Panel).
- **Mobile**: Responsive bottom-sheet navigation and simplified chat cards.

## 4. Scalability Considerations
- **Session Management**: Each chat is a unique session stored in a backend DB (PostgreSQL) rather than local state.
- **User Authentication**: Secure login (OAuth/SSO) to support thousands of users.
- **Rate Limiting Visuals**: Clear indicators of usage limits and tier-based feature access.
- **Latency Handling**: Optimistic UI updates and skeleton screens while waiting for LLM/SQL execution.

## 5. Technical Stack (Frontend)
- **Framework**: Next.js (for routing and SSR) or advanced Streamlit.
- **Components**: Tailwind CSS + Shadcn UI for premium, accessible components.
- **State Management**: React Query (for data fetching) and Zustand (for UI state).
- **Visualization**: Recharts or D3.js.
