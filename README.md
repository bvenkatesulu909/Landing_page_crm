# Landing Page

A modern, responsive landing page with a contact form for collecting customer details.

## Features

- ✨ Clean and professional design
- 📱 Fully responsive (mobile & desktop)
- 🎨 Gradient background with smooth animations
- ✅ Form validation
- 🎯 Success message on submission
- 💾 Customer details saved to a SQLite database by a small Python backend
- 🔐 Admin page to view, search and export customers
- 🤖 MCP server so Claude (or any MCP client) can look up and add customers

## Files

- `index.html` - Full landing page (navbar, hero, stats, features, how it works, testimonials, contact form, footer)
- `landing-page.html` - Standalone contact form page
- `admin.html` - Password-protected admin page: customers with payment status, totals, filters, paging and CSV download
- `scripts/demo_customers.py` - Generates, imports or removes demo customers with payment details
- `server.py` - Python backend that serves the page and stores submissions in `customers.db`
- `mcp_server.py` - MCP server exposing the customer database as tools
- `.mcp.json` - Registers the MCP server with Claude Code for this project
- `netlify/functions/customers.mjs` - The `/api/customers` endpoint for the Netlify deployment (stores data in Netlify Blobs)
- `netlify/functions/chat.mjs` - The `/api/chat` chatbot endpoint (Claude Haiku 5.5)
- `netlify/lib/customers.mjs` - Contact-detail rules and customer storage shared by both functions
- `netlify.toml`, `package.json` - Netlify build settings and function dependencies

## How to Use

Requires Python 3.8+ (standard library only, nothing to install).

1. Clone this repository
2. Start the server:
   ```bash
   python server.py
   ```
3. Open http://localhost:8000 in your browser
4. Fill in the contact form with your name, phone number, email and address and submit it

Submissions are stored in `customers.db` (SQLite) next to `server.py`. The file is created automatically and is ignored by git.

## Viewing Saved Customers

Open `/admin.html` on the site, e.g. http://localhost:8000/admin.html or https://loquacious-dragon-b3a19b.netlify.app/admin.html, and sign in with the admin token. You get every customer in a table with search, Refresh, and **Download CSV**. The token is kept only for that browser tab and is cleared when you sign out.

The admin token is the `ADMIN_TOKEN` environment variable: set it in Netlify under **Project configuration → Environment variables** (then redeploy), or locally when starting the server:

```bash
ADMIN_TOKEN=choose-a-long-secret python server.py
```

Without `ADMIN_TOKEN` set, nobody can sign in. You can also fetch the list directly:

```bash
curl -H "X-Admin-Token: choose-a-long-secret" http://localhost:8000/api/customers
```

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/customers` | Save a customer. JSON body: `name`, `phone`, `email`, `address`. Returns `201`, or `400` with field errors. |
| `GET` | `/api/customers` | List customers. Requires the `X-Admin-Token` header. |

Settings (environment variables): `HOST` (default `127.0.0.1`), `PORT` (default `8000`), `DB_PATH`, `ADMIN_TOKEN`.

## Chatbot

The chat bubble on the landing page talks to `/api/chat`, a Netlify Function that answers with **Claude Haiku 5.5** (`claude-haiku-5-5`) and streams the reply word by word. Visitors can type or use the 🎤 mic (browser speech-to-text, English / Hindi / Telugu), and turn on 🔊 to hear replies.

What the bot can do:

- Answer questions using `BUSINESS_INFO` at the top of `netlify/functions/chat.mjs`: name, plans and prices, payment, hours and FAQs. It is filled from the website today; replace it with your real details. The behaviour rules sit separately in `RULES`. The system prompt is cached, so each message pays the reduced cached-input price for it.
- **`save_lead`** - saves the visitor's name, phone, email and address as a customer (same rules as the contact form, marked `"source": "chat"`). Confirmation is enforced in code: the first call only returns the details for the bot to read back, and they are saved only when the bot sends the identical details again after the visitor has replied. One lead per chat.
- **`request_callback`** - records when and why the visitor wants a call, on that customer.

It has **no tool that reads customer data**, so nothing a visitor types can make it reveal other customers' details.

### Setup on Netlify

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key. Without it the chat replies "unavailable" |
| `CHAT_DAILY_BUDGET_USD` | No | Daily spending limit for Claude usage across all visitors, in US dollars (default 2) |
| `CHAT_HASH_SALT` | No | Secret used to hash visitor IPs for rate limits (raw IPs are never stored) |
| `CHAT_RETENTION_DAYS` | No | How long conversations are kept, from when they started (default 90). If you change it, also change the "kept for 90 days" note in `index.html` |

Add them under **Project configuration -> Environment variables**, then redeploy.

### Limits

- 8 messages a minute and 150 a day per visitor; 1,000 characters per message.
- A daily spending limit: each Claude response's token usage is priced at Claude Haiku 5.5 rates and added to a daily total; once it reaches `CHAT_DAILY_BUDGET_USD`, the bot replies "Please try again later." until the next day (UTC). Replies stopped midway aren't counted, so the real total can run slightly higher.
- 40 messages per conversation, after which the visitor is asked to start a new chat.
- The last 20 exchanges are sent to Claude with each message.

**Reading conversations (admin):** the admin page has a **Chats** tab listing recent conversations, newest first, with badges for captured leads and callback requests. Select one to read the transcript, or use **Open customer** to jump to the customer it created. The same data is available through two read-only endpoints that need `X-Admin-Token`: `GET /api/chats` (summaries) and `GET /api/chats/{id}` (one transcript). Both are served by `netlify/functions/chats-admin.mjs`.

Conversations are stored in the `chats` Blobs store, keyed by the random `chat_id` the widget keeps in the browser. Each record has the chat ID, start time, messages, the lead it created (`lead_id`) and whether a callback was requested (`callback_requested`).

**Retention:** a conversation is kept for `CHAT_RETENTION_DAYS` (default 90) from when it started. The chat function ignores older conversations, and a scheduled function, `netlify/functions/purge-chats.mjs`, runs daily and deletes them. Customer records are not affected. The widget shows the retention period in its note. The widget keeps its own copy for 24 hours of inactivity so a refresh restores the conversation.

## Demo Customers

`scripts/demo_customers.py` creates 1,000 fake customers with payment details so the admin page and MCP tools have realistic data. Each one has a status (Payment completed, Dues pending, Processing transaction or Contacted), a plan, total / paid / due amounts in INR, a due date and the latest transaction (ID, date, amount, method and state). Emails use the reserved `example.com` domain and every record is marked `"is_demo": true`.

Customers who sign up through the website form have no payment details and show as **New lead**.

```bash
python scripts/demo_customers.py generate          # write demo_customers.json to inspect
python scripts/demo_customers.py import            # add them to the live site
python scripts/demo_customers.py delete            # remove every demo customer
```

`import` and `delete` read the admin token from `CUSTOMERS_ADMIN_TOKEN`. Importing again replaces the same batches rather than duplicating them, and `delete` only ever removes demo batches, never website sign-ups.

On Netlify, demo customers are stored in batches of 250 (`batch/demo-01` ... `batch/demo-04`) through two admin-only endpoints:

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/customers/import` | Store a batch: `{ "batch": "demo-01", "customers": [...] }` |
| `DELETE` | `/api/customers/demo` | Remove all demo batches |

## MCP Server

`mcp_server.py` connects MCP clients such as Claude Code to the same `customers.db` the landing page writes to, so customers submitted on the website are available to Claude straight away.

| Tool | What it does |
|---|---|
| `list_customers` | List customers, newest first (`limit`, `offset`, optional `status` and `source` = real/demo) |
| `search_customers` | Find customers by part of their name, phone, email, address or transaction ID |
| `get_customer` | Get one customer by ID |
| `add_customer` | Add a customer (same validation as the website form) |
| `customer_stats` | Totals, real vs demo, counts per status, collected / outstanding / processing amounts, overdue customers |

By default the tools use the local `customers.db`. To use the live Netlify site instead, set these environment variables before starting Claude Code:

| Variable | Value |
|---|---|
| `CUSTOMERS_API_URL` | Your site URL, e.g. `https://your-site.netlify.app` |
| `CUSTOMERS_ADMIN_TOKEN` | The same value as `ADMIN_TOKEN` in Netlify |

### Setup

Create a virtual environment and install the MCP SDK (one time):

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python.exe -m pip install -r requirements-mcp.txt
```

On macOS or Linux use `.venv/bin/python` instead, and change `command` in `.mcp.json` to match.

### Connecting to Claude Code

`.mcp.json` already registers the server as `landing-page-customers`. Open this folder in Claude Code and approve the server when asked; then you can ask things like "how many customers signed up this week?" or "find the customer from Hyderabad".

To use it from another MCP client (e.g. Claude Desktop), point it at the virtual environment's Python with `mcp_server.py` as the argument, using absolute paths.

## Deploying to Netlify

Netlify serves `index.html` and runs `netlify/functions/customers.mjs` as the `/api/customers` endpoint, storing submissions in [Netlify Blobs](https://docs.netlify.com/build/data-and-storage/netlify-blobs/). The Python files are not used on Netlify.

1. In Netlify, choose **Add new project → Import an existing project → GitHub** and pick `Landing_page_crm`. The build settings come from `netlify.toml`.
2. In **Project configuration → Environment variables**, add `ADMIN_TOKEN` with a long random value. It protects the customer list.
3. Deploy. Every push to `main` redeploys automatically.

To list customers on the live site:

```bash
curl -H "X-Admin-Token: your-admin-token" https://your-site.netlify.app/api/customers
```

## Customization

You can customize the landing page by editing:
- **Colors**: Modify the gradient colors in the CSS section
- **Text**: Update the header text and placeholder values
- **Font**: Change the font-family in the CSS
- **Styling**: Adjust padding, margins, and border-radius values

## Browser Support

Works on all modern browsers:
- Chrome
- Firefox
- Safari
- Edge

## License

MIT License - Feel free to use this for your projects!
