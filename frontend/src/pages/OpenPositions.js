import React, { useState, useEffect } from 'react';
import { getOpenPositions, getTodayPositions } from '../utils/api';

export default function OpenPositions() {
  const [open, setOpen] = useState([]);
  const [today, setToday] = useState([]);
  const [tab, setTab] = useState('open');

  const fetch = async () => {
    try {
      const [o, t] = await Promise.all([getOpenPositions(), getTodayPositions()]);
      setOpen(o.data);
      setToday(t.data);
    } catch (e) {}
  };

  useEffect(() => {
    fetch();
    const i = setInterval(fetch, 2000);
    return () => clearInterval(i);
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {['open', 'today'].map(t => (
          <button
            key={t}
            style={{
              ...tabBtn,
              ...(tab === t ? { background: '#1d4ed8', color: '#fff' } : {})
            }}
            onClick={() => setTab(t)}
          >
            {t === 'open' ? `Open (${open.length})` : `Today (${today.length})`}
          </button>
        ))}
      </div>

      {tab === 'open' && (
        <div>
          {open.length === 0 ? (
            <div style={empty}>No open positions</div>
          ) : (
            <table style={table}>
              <thead>
                <tr>
                  {['Symbol', 'Leg', 'Qty', 'Avg Price', 'LTP', 'Live P&L', 'Re-entry', 'ST Dir', 'Time'].map(h => (
                    <th key={h} style={th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {open.map(p => (
                  <tr key={p.id} style={{ borderBottom: '1px solid #1e293b' }}>
                    <td style={td}><code style={{ color: '#60a5fa' }}>{p.symbol}</code></td>
                    <td style={td}>
                      <span style={{
                        ...badge,
                        background: p.leg === 'CE' ? '#1e3a5f' : '#3d1a1a',
                        color: p.leg === 'CE' ? '#60a5fa' : '#f87171'
                      }}>{p.leg}</span>
                    </td>
                    <td style={td}>{p.qty}</td>
                    <td style={td}>₹{p.avg_price?.toFixed(2)}</td>
                    <td style={td}>₹{p.ltp?.toFixed(2) || '--'}</td>
                    <td style={td}>
                      <span style={{ color: p.live_pnl >= 0 ? '#4ade80' : '#f87171', fontWeight: 600 }}>
                        ₹{p.live_pnl?.toFixed(2)}
                      </span>
                    </td>
                    <td style={td}>
                      <span style={badge}>{p.reentry_count + 1}/3</span>
                    </td>
                    <td style={td}>
                      <span style={{
                        color: p.supertrend_direction === 'bullish' ? '#4ade80' : '#f87171',
                        fontSize: 12, fontWeight: 600
                      }}>
                        {p.supertrend_direction === 'bullish' ? '▲' : '▼'} {p.supertrend_direction}
                      </span>
                    </td>
                    <td style={td}>{p.entry_time ? new Date(p.entry_time).toLocaleTimeString() : '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === 'today' && (
        <table style={table}>
          <thead>
            <tr>
              {['Symbol', 'Leg', 'Qty', 'Entry', 'Exit', 'P&L', 'Status', 'Reason', 'Time'].map(h => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {today.map(t => (
              <tr key={t.id} style={{ borderBottom: '1px solid #1e293b' }}>
                <td style={td}><code style={{ color: '#60a5fa' }}>{t.symbol}</code></td>
                <td style={td}>
                  <span style={{ ...badge, background: t.leg === 'CE' ? '#1e3a5f' : '#3d1a1a', color: t.leg === 'CE' ? '#60a5fa' : '#f87171' }}>{t.leg}</span>
                </td>
                <td style={td}>{t.qty}</td>
                <td style={td}>₹{t.entry_price?.toFixed(2)}</td>
                <td style={td}>{t.exit_price ? `₹${t.exit_price?.toFixed(2)}` : '--'}</td>
                <td style={td}>
                  {t.pnl !== null ? (
                    <span style={{ color: t.pnl >= 0 ? '#4ade80' : '#f87171', fontWeight: 600 }}>
                      ₹{t.pnl?.toFixed(2)}
                    </span>
                  ) : '--'}
                </td>
                <td style={td}>
                  <span style={{ ...badge, background: t.status === 'OPEN' ? '#052e16' : '#1e293b', color: t.status === 'OPEN' ? '#4ade80' : '#94a3b8' }}>
                    {t.status}
                  </span>
                </td>
                <td style={td}>{t.exit_reason || '--'}</td>
                <td style={td}>{t.entry_time ? new Date(t.entry_time).toLocaleTimeString() : '--'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const tabBtn = {
  border: '1px solid #334155',
  background: '#1e293b',
  color: '#94a3b8',
  padding: '8px 16px',
  borderRadius: 8,
  cursor: 'pointer',
  fontSize: 13,
};
const table = {
  width: '100%',
  borderCollapse: 'collapse',
  background: '#1e293b',
  borderRadius: 12,
  overflow: 'hidden',
};
const th = {
  padding: '12px 16px',
  textAlign: 'left',
  fontSize: 11,
  color: '#64748b',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: 0.5,
  background: '#0f172a',
};
const td = { padding: '12px 16px', fontSize: 13, color: '#e2e8f0' };
const badge = {
  padding: '2px 8px',
  borderRadius: 4,
  fontSize: 11,
  fontWeight: 600,
  background: '#1e293b',
  color: '#94a3b8',
};
const empty = {
  textAlign: 'center',
  padding: 60,
  color: '#64748b',
  background: '#1e293b',
  borderRadius: 12,
};
