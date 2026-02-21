import React, { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import OpenPositions from './pages/OpenPositions';
import PnLHistory from './pages/PnLHistory';
import Profile from './pages/Profile';
import { getStatus } from './utils/api';

const TABS = [
  { id: 'dashboard', label: '📊 Dashboard' },
  { id: 'positions', label: '📋 Open Positions' },
  { id: 'pnl', label: '💰 P&L History' },
  { id: 'profile', label: '⚙️ Profile' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isRunning, setIsRunning] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const { data } = await getStatus();
        setIsRunning(data.is_running);
        setLastUpdate(new Date().toLocaleTimeString());
      } catch (e) {}
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={styles.app}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.logo}>⚡ NIFTY Options Bot</span>
          <span style={{
            ...styles.statusBadge,
            background: isRunning ? '#00ff88' : '#ff4444',
            color: isRunning ? '#000' : '#fff'
          }}>
            {isRunning ? '🟢 LIVE' : '🔴 STOPPED'}
          </span>
        </div>
        <div style={styles.headerRight}>
          <span style={styles.time}>
            🕐 {new Date().toLocaleDateString('en-IN')} | {lastUpdate || '--:--:--'}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div style={styles.tabBar}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            style={{
              ...styles.tab,
              ...(activeTab === tab.id ? styles.activeTab : {})
            }}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={styles.content}>
        {activeTab === 'dashboard' && <Dashboard setIsRunning={setIsRunning} />}
        {activeTab === 'positions' && <OpenPositions />}
        {activeTab === 'pnl' && <PnLHistory />}
        {activeTab === 'profile' && <Profile />}
      </div>
    </div>
  );
}

const styles = {
  app: {
    minHeight: '100vh',
    background: '#0a0e1a',
    color: '#e2e8f0',
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
  },
  header: {
    background: 'linear-gradient(135deg, #1a1f35 0%, #0f172a 100%)',
    borderBottom: '1px solid #1e293b',
    padding: '12px 24px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: 16 },
  logo: { fontSize: 20, fontWeight: 700, color: '#60a5fa' },
  statusBadge: {
    padding: '4px 12px',
    borderRadius: 20,
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: 1,
  },
  headerRight: { color: '#64748b', fontSize: 13 },
  time: { fontFamily: 'monospace' },
  tabBar: {
    display: 'flex',
    background: '#0f172a',
    borderBottom: '1px solid #1e293b',
    padding: '0 16px',
    gap: 4,
  },
  tab: {
    background: 'none',
    border: 'none',
    color: '#64748b',
    padding: '14px 20px',
    cursor: 'pointer',
    fontSize: 14,
    fontWeight: 500,
    borderBottom: '3px solid transparent',
    transition: 'all 0.2s',
  },
  activeTab: {
    color: '#60a5fa',
    borderBottom: '3px solid #60a5fa',
  },
  content: { padding: 24 },
};
