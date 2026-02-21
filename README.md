# NIFTY Options Trading Bot

A full-stack automated trading system for NIFTY options using Fyers API v3, Supertrend strategy, with a professional React terminal dashboard.

---

## 📁 Folder Structure

```
trading-system/
├── backend/
│   ├── main.py                  # FastAPI app, all REST endpoints
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── config/
│   │   └── settings.py          # Pydantic settings (env-based)
│   ├── database/
│   │   ├── models.py            # SQLAlchemy async models
│   │   └── operations.py       # DB CRUD operations
│   ├── services/
│   │   ├── fyers_service.py     # Fyers API v3 + WebSocket
│   │   ├── order_service.py    # Order execution + dedup
│   │   └── orchestrator.py     # Master trading controller
│   ├── strategy/
│   │   ├── supertrend.py        # Supertrend (10,3) calculator
│   │   └── engine.py            # Strategy logic (candle buffer, signals)
│   ├── telegram/
│   │   └── service.py           # Telegram notifications
│   └── utils/
├── frontend/
│   ├── package.json
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
│       ├── App.js               # Tab navigation
│       ├── index.js
│       ├── pages/
│       │   ├── Dashboard.js     # Live market data + controls
│       │   ├── OpenPositions.js # Open + today's trades
│       │   ├── PnLHistory.js    # P&L + equity chart + CSV export
│       │   └── Profile.js       # Credentials + risk settings
│       └── utils/
│           └── api.js           # Axios API calls
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🚀 Quick Start (Docker)

### Prerequisites
- Docker Desktop or Docker + Docker Compose
- Fyers trading account with API access

### 1. Clone and configure
```bash
git clone <your-repo>
cd trading-system
cp .env.example .env
# Edit .env if needed
```

### 2. Start all services
```bash
docker-compose up --build -d
```

### 3. Access the dashboard
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## 🔑 Fyers API Setup

### Get Access Token

Fyers uses OAuth2. Here's how to get your access token:

```python
# Run this once to get access token
from fyers_apiv3 import fyersModel

client_id = "YOUR_CLIENT_ID-100"
secret_key = "YOUR_SECRET_KEY"
redirect_uri = "https://your-redirect-uri.com"

session = fyersModel.SessionModel(
    client_id=client_id,
    secret_key=secret_key,
    redirect_uri=redirect_uri,
    response_type="code",
    grant_type="authorization_code"
)

# Step 1: Get auth URL
auth_url = session.generate_authcode()
print("Visit:", auth_url)

# Step 2: After login, extract auth_code from redirected URL
auth_code = input("Enter auth code: ")
session.set_token(auth_code)
response = session.generate_token()
access_token = response["access_token"]
print("Access Token:", access_token)
```

**Token validity**: Tokens expire daily. You must refresh each trading day.

---

## ⚙️ Strategy Details

### Supertrend (10,3)
- Period: 10 candles, Multiplier: 3.0
- Calculated internally on 3-minute closed candles
- Data source: Fyers WebSocket (live ticks aggregated into 3-min OHLC)

### Entry Rules
- When candle **closes below Supertrend** → **SELL** that option
- Both CE and PE signals trigger independently
- Entry allowed until **2:45 PM** only

### Stop Loss
- Exit when candle **closes above Supertrend**
- Closing basis only (not intrabar)

### Re-entry Scaling
| Entry # | Qty Multiplier |
|---------|---------------|
| 1st     | 1X (base qty) |
| 2nd     | 2X            |
| 3rd     | 3X            |
| After 3rd SL | Stop that leg |

### Intraday Rules
- No overnight positions
- Force square-off at **3:15 PM**
- Daily P&L summary sent to Telegram at **3:20 PM**

---

## 📊 Database Schema

### PostgreSQL Tables

```sql
-- trades: All trade records
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    date TIMESTAMP,
    symbol VARCHAR(50),
    leg VARCHAR(10),           -- CE or PE
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    qty INTEGER,
    entry_price FLOAT,
    exit_price FLOAT,
    pnl FLOAT,
    exit_reason VARCHAR(50),   -- SL, FORCE, MANUAL
    reentry_count INTEGER,
    status VARCHAR(20),        -- OPEN, CLOSED
    order_id VARCHAR(50),
    fyers_order_id VARCHAR(50)
);

-- daily_pnl: Daily summary
CREATE TABLE daily_pnl (
    id SERIAL PRIMARY KEY,
    date TIMESTAMP UNIQUE,
    total_pnl FLOAT,
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    max_drawdown FLOAT
);

-- strategy_logs: All system events
CREATE TABLE strategy_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    level VARCHAR(10),
    message TEXT,
    data JSONB
);

-- reentry_tracking: Per-leg reentry counters
CREATE TABLE reentry_tracking (
    id SERIAL PRIMARY KEY,
    date TIMESTAMP,
    leg VARCHAR(10),
    reentry_count INTEGER,
    is_stopped BOOLEAN,
    last_updated TIMESTAMP
);

-- app_config: Credentials and settings (key-value)
CREATE TABLE app_config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE,
    value TEXT,
    updated_at TIMESTAMP
);
```

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard` | Live dashboard data |
| GET | `/api/trading/status` | System status |
| POST | `/api/trading/start` | Start bot with credentials |
| POST | `/api/trading/stop` | Stop bot |
| GET | `/api/positions/open` | Open positions |
| GET | `/api/positions/today` | Today's trades |
| GET | `/api/pnl/history` | Daily P&L history |
| GET | `/api/pnl/trades` | All trades |
| POST | `/api/profile/save` | Save credentials |
| GET | `/api/profile` | Get profile |
| POST | `/api/profile/test-telegram` | Test Telegram |
| GET | `/api/settings/risk` | Get risk settings |
| POST | `/api/settings/risk` | Update risk settings |

---

## ☁️ Deployment

### AWS EC2

```bash
# Install Docker on EC2 (Amazon Linux 2)
sudo yum update -y
sudo yum install docker -y
sudo service docker start
sudo usermod -a -G docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone repo
git clone <your-repo>
cd trading-system
cp .env.example .env
docker-compose up -d

# Open ports in Security Group: 3000, 8000
```

### Render

Create two services:
1. **Web Service** (backend): Docker, root dir `backend/`, port 8000
2. **Static Site** (frontend): Build command `npm run build`, publish `build/`

Set environment variables: `DATABASE_URL` pointing to a Render PostgreSQL instance.

### Railway

```bash
# Install Railway CLI
npm i -g @railway/cli
railway login
railway init
railway up
```

Add PostgreSQL plugin in Railway dashboard, then set `DATABASE_URL` from the plugin.

---

## 🛡️ Security Notes

- Credentials stored in PostgreSQL `app_config` table (not in env files)
- Secret key shown masked in UI (last 4 chars only)
- No hardcoded API keys anywhere in codebase
- Tokens expire daily and must be refreshed by the user

---

## 📱 Telegram Notification Examples

```
📥 ORDER PLACED
Symbol: NSE:NIFTY25JAN2422500CE
Action: SELL CE
Qty: 50
Price: ₹112.50
Time: 10:23:45

🛑 SL HIT
NIFTY CE SL HIT
Exit Price: ₹124.30
PnL: ₹-587.00

🔄 RE-ENTRY #2
Symbol: NSE:NIFTY25JAN2422500CE
Qty: 100 (2X)
Price: ₹108.75

🟢 DAILY SUMMARY - 25 Jan 2025
Total PnL: ₹2,450.00
Total Trades: 6
Winning: 4 | Losing: 2
Win Rate: 66.7%
```

---

## 🔧 Local Development (without Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
# Set DATABASE_URL in .env
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
REACT_APP_API_URL=http://localhost:8000/api npm start
```
