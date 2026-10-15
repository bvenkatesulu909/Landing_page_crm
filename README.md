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
- `admin.html` - Password-protected admin page listing all customers, with search and CSV download
- `server.py` - Python backend that serves the page and stores submissions in `customers.db`
- `mcp_server.py` - MCP server exposing the customer database as tools
- `.mcp.json` - Registers the MCP server with Claude Code for this project
- `netlify/functions/customers.mjs` - The `/api/customers` endpoint for the Netlify deployment (stores data in Netlify Blobs)
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

## MCP Server

`mcp_server.py` connects MCP clients such as Claude Code to the same `customers.db` the landing page writes to, so customers submitted on the website are available to Claude straight away.

| Tool | What it does |
|---|---|
| `list_customers` | List customers, newest first (`limit`, `offset`) |
| `search_customers` | Find customers by part of their name, phone, email or address |
| `get_customer` | Get one customer by ID |
| `add_customer` | Add a customer (same validation as the website form) |
| `customer_stats` | Total submissions, last 24 hours, last 7 days, latest submission |

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
