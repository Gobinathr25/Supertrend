import hashlib
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Callable
import httpx

logger = logging.getLogger(__name__)
FYERS_API_URL = "https://api-t1.fyers.in/api/v3"

_auth_server: Optional[HTTPServer] = None


class _CallbackHandler(BaseHTTPRequestHandler):
    on_code: Optional[Callable] = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        auth_code = (params.get("auth_code") or params.get("code") or [None])[0]
        s_val     = (params.get("s") or ["ok"])[0]

        if auth_code and s_val != "error":
            html = _page("success", "✅ Login Successful!", "Session created. This window will close automatically.")
        else:
            auth_code = None
            html = _page("error", "❌ Login Failed", "Please close this window and try again.")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(html.encode())

        if self.on_code:
            threading.Thread(target=self.on_code, args=(auth_code,), daemon=True).start()

    def log_message(self, *args):
        pass


def _page(status, title, body):
    color = "#4ade80" if status == "success" else "#f87171"
    bg    = "#052e16" if status == "success" else "#2d0000"
    bd    = "#16a34a" if status == "success" else "#dc2626"
    return f"""<!DOCTYPE html><html><head><title>Fyers Auth</title>
<style>body{{margin:0;background:#0a0e1a;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:'Segoe UI',sans-serif}}
.b{{background:{bg};border:1px solid {bd};border-radius:16px;padding:40px 60px;text-align:center;max-width:400px}}
h2{{color:{color};margin-bottom:12px}}p{{color:#e2e8f0;font-size:15px;margin-bottom:20px}}
button{{background:{color};color:#000;border:none;border-radius:8px;padding:10px 24px;font-size:14px;font-weight:700;cursor:pointer}}</style>
</head><body><div class="b"><h2>{title}</h2><p>{body}</p>
<button onclick="window.close()">Close Window</button></div>
<script>
if(window.opener){{window.opener.postMessage(JSON.stringify({{type:'fyers_auth',status:'{status}'}}),'*');}}
setTimeout(()=>window.close(),2500);
</script></body></html>"""


class FyersAuth:
    LOCAL_PORT   = 8765
    LOCAL_URI    = f"http://localhost:{LOCAL_PORT}"

    def __init__(self, app_id: str = "", secret_id: str = "", redirect_uri: str = ""):
        self.app_id      = app_id
        self.secret_id   = secret_id
        # Use provided redirect_uri or fall back to localhost
        self.redirect_uri = redirect_uri.rstrip("/") if redirect_uri else self.LOCAL_URI

    def get_auth_url(self) -> str:
        try:
            from fyers_apiv3 import fyersModel
            session = fyersModel.SessionModel(
                client_id    = self.app_id,
                secret_key   = self.secret_id,
                redirect_uri = self.redirect_uri,
                response_type= "code",
                grant_type   = "authorization_code",
                state        = "trading_bot"
            )
            url = session.generate_authcode()
            logger.info(f"Auth URL: {url}")
            return url
        except Exception as e:
            raise Exception(f"Could not generate Fyers login URL: {e}")

    async def exchange_code(self, auth_code: str) -> Optional[str]:
        try:
            from fyers_apiv3 import fyersModel
            session = fyersModel.SessionModel(
                client_id    = self.app_id,
                secret_key   = self.secret_id,
                redirect_uri = self.redirect_uri,
                response_type= "code",
                grant_type   = "authorization_code"
            )
            session.set_token(auth_code)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, session.generate_token)
            logger.info(f"Token response: {response}")
            if response.get("s") == "ok":
                return response.get("access_token")
            logger.error(f"Token exchange failed: {response}")
            return None
        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            return None

    async def validate_token(self, client_id: str, access_token: str) -> bool:
        headers = {"Authorization": f"{client_id}:{access_token}"}
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{FYERS_API_URL}/profile", headers=headers, timeout=10)
                return r.status_code == 200
        except Exception:
            return False


def start_local_callback_server(on_code: Callable) -> bool:
    """Start local HTTP server on port 8765 to capture OAuth redirect."""
    global _auth_server
    try:
        stop_local_callback_server()  # Clean up any existing server

        class Handler(_CallbackHandler):
            pass
        Handler.on_code = on_code

        _auth_server = HTTPServer(("0.0.0.0", FyersAuth.LOCAL_PORT), Handler)
        t = threading.Thread(target=_auth_server.serve_forever, daemon=True)
        t.start()
        logger.info(f"Local callback server started on port {FyersAuth.LOCAL_PORT}")
        return True
    except OSError as e:
        logger.error(f"Could not start local server: {e}")
        return False


def stop_local_callback_server():
    global _auth_server
    if _auth_server:
        try:
            _auth_server.shutdown()
        except Exception:
            pass
        _auth_server = None
