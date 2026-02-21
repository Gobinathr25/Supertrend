import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

// Reset CSS
const style = document.createElement('style');
style.textContent = `* { margin: 0; padding: 0; box-sizing: border-box; } body { background: #0a0e1a; }`;
document.head.appendChild(style);

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
