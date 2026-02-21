import React, { useState, useEffect } from 'react';
import { saveProfile, testTelegram, getProfile, getRiskSettings, updateRiskSettings } from '../utils/api';

const Field = ({ label, type = 'text', value, onChange, placeholder }) => (
  <div style={{ marginBottom: 16 }}>
    <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 6 }}>{label}</label>
    <input
      type={type}
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: '100%',
        background: '#0f172a',
        border: '1px solid #334155',
        borderRadius: 8,
        padding: '10px 12px',
        color: '#e2e8f0',
        fontSize: 14,
        boxSizing: 'border-box',
      }}
    />
  </div>
);

export default function Profile() {
  const [profile, setProfile] = useState({
    client_id: '', secret_key: '', access_token: '',
    telegram_token: '', telegram_chat_id: ''
  });
  const [risk, setRisk] = useState({
    max_daily_loss: 10000, max_trades_per_day: 20, lot_size: 50, scaling_enabled: true
  });
  const [msg, setMsg] = useState('');
  const [riskMsg, setRiskMsg] = useState('');
  const [tgMsg, setTgMsg] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getProfile().then(r => {
      setProfile(prev => ({ ...prev, ...r.data }));
    }).catch(() => {});
    getRiskSettings().then(r => setRisk(r.data)).catch(() => {});
  }, []);

  const handleSaveProfile = async () => {
    setLoading(true);
    try {
      await saveProfile(profile);
      setMsg('✅ Profile saved successfully');
    } catch (e) {
      setMsg('❌ Failed to save profile');
    }
    setLoading(false);
    setTimeout(() => setMsg(''), 3000);
  };

  const handleTestTelegram = async () => {
    try {
      await saveProfile(profile);
      const { data } = await testTelegram();
      setTgMsg(data.success ? '✅ Telegram connected!' : '❌ Telegram failed');
    } catch (e) {
      setTgMsg('❌ Error testing Telegram');
    }
    setTimeout(() => setTgMsg(''), 4000);
  };

  const handleSaveRisk = async () => {
    try {
      await updateRiskSettings(risk);
      setRiskMsg('✅ Risk settings updated');
    } catch (e) {
      setRiskMsg('❌ Failed to update');
    }
    setTimeout(() => setRiskMsg(''), 3000);
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
      {/* Fyers Credentials */}
      <div style={card}>
        <div style={title}>🔑 Fyers Credentials</div>
        <div style={{ background: '#0f172a', border: '1px solid #1e3a5f', borderRadius: 8, padding: 12, marginBottom: 16, fontSize: 12, color: '#60a5fa' }}>
          ℹ️ Get your access token from Fyers API dashboard after OAuth login.
          Credentials are stored encrypted in the database.
        </div>
        <Field label="Client ID" value={profile.client_id} onChange={v => setProfile({ ...profile, client_id: v })} placeholder="XXXX-100" />
        <Field label="Secret Key" type="password" value={profile.secret_key} onChange={v => setProfile({ ...profile, secret_key: v })} placeholder="Your secret key" />
        <Field label="Access Token" type="password" value={profile.access_token} onChange={v => setProfile({ ...profile, access_token: v })} placeholder="Your access token" />
        {msg && <div style={{ color: msg.startsWith('✅') ? '#4ade80' : '#f87171', marginBottom: 12, fontSize: 13 }}>{msg}</div>}
        <button style={btnPrimary} onClick={handleSaveProfile} disabled={loading}>
          {loading ? '⏳ Saving...' : '💾 Save Credentials'}
        </button>
      </div>

      {/* Telegram */}
      <div style={card}>
        <div style={title}>📱 Telegram Notifications</div>
        <div style={{ background: '#0f172a', border: '1px solid #1e3a5f', borderRadius: 8, padding: 12, marginBottom: 16, fontSize: 12, color: '#60a5fa' }}>
          ℹ️ Create a bot via @BotFather and get your Chat ID from @userinfobot
        </div>
        <Field label="Bot Token" type="password" value={profile.telegram_token} onChange={v => setProfile({ ...profile, telegram_token: v })} placeholder="123456:ABC-DEF..." />
        <Field label="Chat ID" value={profile.telegram_chat_id} onChange={v => setProfile({ ...profile, telegram_chat_id: v })} placeholder="-100123456789" />
        {tgMsg && <div style={{ color: tgMsg.startsWith('✅') ? '#4ade80' : '#f87171', marginBottom: 12, fontSize: 13 }}>{tgMsg}</div>}
        <button style={{ ...btnPrimary, background: '#1d4ed8' }} onClick={handleTestTelegram}>
          🧪 Save & Test Connection
        </button>
      </div>

      {/* Risk Settings */}
      <div style={{ ...card, gridColumn: '1 / -1' }}>
        <div style={title}>🛡️ Risk Management</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          <div>
            <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 6 }}>Max Daily Loss (₹)</label>
            <input
              type="number"
              value={risk.max_daily_loss}
              onChange={e => setRisk({ ...risk, max_daily_loss: Number(e.target.value) })}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 6 }}>Max Trades/Day</label>
            <input
              type="number"
              value={risk.max_trades_per_day}
              onChange={e => setRisk({ ...risk, max_trades_per_day: Number(e.target.value) })}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 6 }}>Lot Size (qty)</label>
            <input
              type="number"
              value={risk.lot_size}
              onChange={e => setRisk({ ...risk, lot_size: Number(e.target.value) })}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 6 }}>Scaling (1X→2X→3X)</label>
            <div
              style={{
                ...inputStyle,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                cursor: 'pointer',
              }}
              onClick={() => setRisk({ ...risk, scaling_enabled: !risk.scaling_enabled })}
            >
              <span>{risk.scaling_enabled ? '✅ Enabled' : '❌ Disabled'}</span>
              <span style={{ fontSize: 20 }}>{risk.scaling_enabled ? '🟢' : '🔴'}</span>
            </div>
          </div>
        </div>
        {riskMsg && <div style={{ color: riskMsg.startsWith('✅') ? '#4ade80' : '#f87171', margin: '12px 0', fontSize: 13 }}>{riskMsg}</div>}
        <button style={{ ...btnPrimary, marginTop: 16, background: '#7c3aed' }} onClick={handleSaveRisk}>
          💾 Save Risk Settings
        </button>
      </div>
    </div>
  );
}

const card = { background: '#1e293b', borderRadius: 12, padding: 24, border: '1px solid #334155' };
const title = { color: '#94a3b8', fontSize: 13, fontWeight: 600, marginBottom: 20, textTransform: 'uppercase', letterSpacing: 0.5 };
const btnPrimary = { background: '#16a34a', border: 'none', borderRadius: 8, padding: '10px 20px', color: '#fff', fontSize: 14, fontWeight: 600, cursor: 'pointer' };
const inputStyle = { width: '100%', background: '#0f172a', border: '1px solid #334155', borderRadius: 8, padding: '10px 12px', color: '#e2e8f0', fontSize: 14, boxSizing: 'border-box' };
