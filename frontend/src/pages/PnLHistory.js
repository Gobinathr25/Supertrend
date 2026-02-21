import React, { useState, useEffect } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import { getPnLHistory, getAllTrades } from '../utils/api';

export default function PnLHistory() {
  const [history, setHistory] = useState([]);
  const [trades, setTrades] = useState([]);
  const [view, setView] = useState('chart');

  useEffect(() => {
    getPnLHistory().then(r => setHistory(r.data)).catch(() => {});
    getAllTrades().then(r => setTrades(r.data)).catch(() => {});
  }, []);

  const exportCSV = () => {
    const headers = ['Date', 'Symbol', 'Leg', 'Qty', 'Entry', 'Exit', 'PnL', 'Reason', 'Status'];
    const rows = trades.map(t => [
      t.date, t.symbol, t.leg, t.qty,
      t.entry_price, t.exit_price, t.pnl, t.exit_reason, t.status
    ]);
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'trades.csv'; a.click();
  };

  // Cumulative equity
  const chartData = [...history].reverse().map((d, i, arr) => ({
    date: d.date,
    pnl: d.total_pnl,
    cumulative: arr.slice(0, i + 1).reduce((s, x) => s + x.total_pnl, 0)
  }));

  const totalPnl = history.reduce((s, d) => s + d.total_pnl, 0);
  const totalTrades = history.reduce((s, d) => s + d.total_trades, 0);
  const winRate = history.length
    ? (history.reduce((s, d) => s + d.winning_trades, 0) / totalTrades * 100).toFixed(1)
    : 0;

  return (
    <div>
      {/* Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 20 }}>
        {[
          { label: 'Total P&L', value: `₹${totalPnl.toFixed(2)}`, color: totalPnl >= 0 ? '#4ade80' : '#f87171' },
          { label: 'Total Trades', value: totalTrades, color: '#60a5fa' },
          { label: 'Win Rate', value: `${winRate}%`, color: '#f59e0b' },
          { label: 'Trading Days', value: history.length, color: '#c084fc' },
        ].map(s => (
          <div key={s.label} style={card}>
            <div style={{ color: '#64748b', fontSize: 12, marginBottom: 4 }}>{s.label}</div>
            <div style={{ color: s.color, fontSize: 22, fontWeight: 700 }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* View toggle + export */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          {['chart', 'daily', 'trades'].map(v => (
            <button
              key={v}
              style={{ ...tabBtn, ...(view === v ? { background: '#1d4ed8', color: '#fff' } : {}) }}
              onClick={() => setView(v)}
            >
              {v === 'chart' ? '📊 Equity Curve' : v === 'daily' ? '📅 Daily' : '📝 Trades'}
            </button>
          ))}
        </div>
        <button style={{ ...tabBtn, background: '#065f46', color: '#4ade80' }} onClick={exportCSV}>
          ⬇ Export CSV
        </button>
      </div>

      {view === 'chart' && (
        <div style={card}>
          <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 16 }}>Cumulative Equity Curve</div>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Area
                type="monotone"
                dataKey="cumulative"
                stroke="#60a5fa"
                fill="url(#grad)"
                strokeWidth={2}
              />
              <defs>
                <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#60a5fa" stopOpacity={0} />
                </linearGradient>
              </defs>
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {view === 'daily' && (
        <table style={table}>
          <thead>
            <tr>
              {['Date', 'Total P&L', 'Trades', 'Win', 'Loss', 'Win Rate'].map(h => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {history.map(d => (
              <tr key={d.date} style={{ borderBottom: '1px solid #0f172a' }}>
                <td style={td}>{d.date}</td>
                <td style={td}>
                  <span style={{ color: d.total_pnl >= 0 ? '#4ade80' : '#f87171', fontWeight: 600 }}>
                    ₹{d.total_pnl.toFixed(2)}
                  </span>
                </td>
                <td style={td}>{d.total_trades}</td>
                <td style={{ ...td, color: '#4ade80' }}>{d.winning_trades}</td>
                <td style={{ ...td, color: '#f87171' }}>{d.losing_trades}</td>
                <td style={td}>
                  {d.total_trades > 0 ? `${(d.winning_trades / d.total_trades * 100).toFixed(1)}%` : '--'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {view === 'trades' && (
        <table style={table}>
          <thead>
            <tr>
              {['Date', 'Symbol', 'Leg', 'Qty', 'Entry', 'Exit', 'P&L', 'Reason'].map(h => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trades.map(t => (
              <tr key={t.id} style={{ borderBottom: '1px solid #0f172a' }}>
                <td style={td}>{t.date}</td>
                <td style={td}><code style={{ color: '#60a5fa', fontSize: 11 }}>{t.symbol}</code></td>
                <td style={td}>
                  <span style={{ color: t.leg === 'CE' ? '#60a5fa' : '#f87171' }}>{t.leg}</span>
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
                <td style={td}>{t.exit_reason || '--'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const card = { background: '#1e293b', borderRadius: 12, padding: 20, border: '1px solid #334155' };
const tabBtn = { border: '1px solid #334155', background: '#1e293b', color: '#94a3b8', padding: '8px 14px', borderRadius: 8, cursor: 'pointer', fontSize: 13 };
const table = { width: '100%', borderCollapse: 'collapse', background: '#1e293b', borderRadius: 12, overflow: 'hidden' };
const th = { padding: '12px 16px', textAlign: 'left', fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', background: '#0f172a' };
const td = { padding: '12px 16px', fontSize: 13, color: '#e2e8f0' };
