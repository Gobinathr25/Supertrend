import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
});

export const getDashboard = () => api.get('/dashboard');
export const getStatus = () => api.get('/trading/status');
export const getOpenPositions = () => api.get('/positions/open');
export const getTodayPositions = () => api.get('/positions/today');
export const getPnLHistory = () => api.get('/pnl/history');
export const getAllTrades = () => api.get('/pnl/trades');
export const getProfile = () => api.get('/profile');
export const getRiskSettings = () => api.get('/settings/risk');

export const startTrading = (payload) => api.post('/trading/start', payload);
export const stopTrading = () => api.post('/trading/stop');
export const saveProfile = (payload) => api.post('/profile/save', payload);
export const testTelegram = () => api.post('/profile/test-telegram');
export const updateRiskSettings = (payload) => api.post('/settings/risk', payload);

export default api;
