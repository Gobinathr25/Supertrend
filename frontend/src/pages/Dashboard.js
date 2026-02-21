import React, { useState, useEffect } from 'react';
import { getDashboard, startTrading, stopTrading } from '../utils/api';

const Card = ({ title, children, style = {} }) => (
  <div style={{ ...cardStyle, ...style }}>
    {title && <div style={cardTitle}>{title}</div>}
    {children}
  </div>
);

const StatBox = ({ label, value, sub, color = '#60a5fa' }) => (
  <div style={statBox}>
    <div style={{ fontSize: 12, color: '#64748b', marginBottom: 4 }}>{label}</div>
    <div style={{ fontSize: 24, fontWeight: 700, color, fontFamily: 'monospace' }}>{value}</div>
    {sub && <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>{sub}</div>}
  </div>
);

const STBadge = ({ direction, value, distance, signalTime }) => {
  const bull = direction === 'bullish';
  return (
    <div style={{
      background: bull ? '#052e16' : '#2d0000',
      border: `1px solid ${bull ? '#16a34a' : '#dc2626'}`,
      borderRadius: 8,
      padding: '12px 16px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 18, fontWeight: 700, color: bull ? '#4ade80' : '#f87171' }}>
          {bull ? '▲ BULLISH' : '▼ BEARISH'}
        </span>
        <span style={{ fontSize: 12, color: '#64748b' }}>
          {direction === 'unknown' ? 'Waiting...' : `ST: ${value?.toFixed(2)}`}
        </span>
      </div>
      {distance !== undefined && (
        <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
          Distance: {distance?.toFixed(2)} | {signalTime ? `Signal: ${signalTime}` : 'No signal yet'}
        </div>
      )}
    </div>
  );
};

export default function Dashboard({ setIsRunning }) {
  const [data, setData] = useState(null);
  const [creds, setCreds] = useState({ client_id: '', access_token: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetch = async () => {
    try {
      const { data: d } = await getDashboard();
      setData(d);
      setIsRunning(d.is_running);
    } catch (e) {}
  };

  useEffect(() => {
    fetch();
    const i = setInterval(fetch, 2000);
    return () => clearInterval(i);
  }, []);

  const handleStart = async () => {
    if (!creds.client_id || !creds.access_token) {
      setError('Client ID and Access Token are required');
      return;
    }
    setLoading(true); setError('');
    try {
      await startTrading({ ...creds, lot_size: 50 });
      await fetch();
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to start trading');
    }
    setLoading(false);
  };

  const handleStop = async () => {
    await stopTrading();
    await fetch();
  };

  const pnl = data?.daily_pnl || 0;

  return (
    <div>
      <div style={grid2}>
        {/* Market Data */}
        <Card title="📈 Market Overview">
          <div style={grid2}>
            <StatBox
              label="NIFTY 50"
              value={data?.nifty_spot?.toLocaleString('en-IN') || '--'}
              color="#60a5fa"
            />
            <StatBox
              label="SENSEX"
              value={data?.sensex_spot?.toLocaleString('en-IN') || '--'}
              color="#818cf8"
            />
            <StatBox
              label="ATM Strike"
              value={data?.atm_strike || '--'}
              color="#f59e0b"
            />
            <StatBox
              label="Today's P&L"
              value={`₹${pnl.toFixed(0)}`}
              color={pnl >= 0 ? '#4ade80' : '#f87171'}
            />
          </div>
        </Card>

        {/* Margin */}
        <Card title="💼 Margin Summary">
          <div style={grid2}>
            <StatBox
              label="Available"
              value={`₹${(data?.available_margin || 0).toLocaleString('en-IN')}`}
              color="#4ade80"
            />
            <StatBox
              label="Used"
              value={`₹${(data?.used_margin || 0).toLocaleString('en-IN')}`}
              color="#f59e0b"
            />
            <StatBox
              label="Daily Trades"
              value={data?.daily_trades || 0}
              color="#c084fc"
            />
            <StatBox
              label="Open Positions"
              value={data?.open_positions_count || 0}
              color="#38bdf8"
            />
          </div>
        </Card>
      </div>

      {/* Supertrend */}
      <Card title="🔮 Supertrend Status (10,3)" style={{ marginTop: 16 }}>
        <div style={grid2}>
          <div>
            <div style={{ marginBottom: 8, color: '#94a3b8', fontSize: 12 }}>CE LEG</div>
            <STBadge
              direction={data?.ce_supertrend?.direction || 'unknown'}
              value={data?.ce_supertrend?.value}
              distance={data?.ce_supertrend?.distance}
              signalTime={data?.ce_supertrend?.signal_time}
            />
          </div>
          <div>
            <div style={{ marginBottom: 8, color: '#94a3b8', fontSize: 12 }}>PE LEG</div>
            <STBadge
              direction={data?.pe_supertrend?.direction || 'unknown'}
              value={data?.pe_supertrend?.value}
              distance={data?.pe_supertrend?.distance}
              signalTime={data?.pe_supertrend?.signal_time}
            />
          </div>
        </div>
      </Card>

      {/* Controls */}
      <Card title="🚀 Trading Controls" style={{ marginTop: 16 }}>
        {!data?.is_running ? (
          <div>
            <div style={grid2}>
              <div>
                <label style={label}>Client ID</label>
                <input
                  style={input}
                  placeholder="Your Fyers Client ID"
                  value={creds.client_id}
                  onChange={e => setCreds({ ...creds, client_id: e.target.value })}
                />
              </div>
              <div>
                <label style={label}>Access Token</label>
                <input
                  style={input}
                  type="password"
                  placeholder="Fyers Access Token"
                  value={creds.access_token}
                  onChange={e => setCreds({ ...creds, access_token: e.target.value })}
                />
              </div>
            </div>
            {error && <div style={{ color: '#f87171', marginTop: 8, fontSize: 13 }}>{error}</div>}
            <button
              style={{ ...btn, background: '#16a34a', marginTop: 12, opacity: loading ? 0.6 : 1 }}
              onClick={handleStart}
              disabled={loading}
            >
              {loading ? '⏳ Starting...' : '▶ Start Trading'}
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ color: '#4ade80', fontWeight: 600 }}>
              ✅ System Active — CE: {data?.ce_symbol} | PE: {data?.pe_symbol}
            </div>
            <button
              style={{ ...btn, background: '#dc2626' }}
              onClick={handleStop}
            >
              ⏹ Stop
            </button>
          </div>
        )}
      </Card>
    </div>
  );
}

const cardStyle = {
  background: '#1e293b',
  borderRadius: 12,
  padding: 20,
  border: '1px solid #334155',
};
const cardTitle = {
  color: '#94a3b8',
  fontSize: 13,
  fontWeight: 600,
  marginBottom: 16,
  textTransform: 'uppercase',
  letterSpacing: 0.5,
};
const grid2 = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 };
const statBox = {
  background: '#0f172a',
  borderRadius: 8,
  padding: '12px 16px',
};
const label = { display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 6 };
const input = {
  width: '100%',
  background: '#0f172a',
  border: '1px solid #334155',
  borderRadius: 8,
  padding: '10px 12px',
  color: '#e2e8f0',
  fontSize: 14,
  boxSizing: 'border-box',
};
const btn = {
  border: 'none',
  borderRadius: 8,
  padding: '10px 24px',
  color: '#fff',
  fontSize: 14,
  fontWeight: 600,
  cursor: 'pointer',
};
