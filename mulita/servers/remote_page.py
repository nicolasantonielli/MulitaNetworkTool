"""Browser client and loopback transport for the operator's live Qt session."""
import json
import os
import socket


def forward(message):
    endpoint = os.environ.get('MULITA_CONTROL_PORT')
    if not endpoint:
        return 503, b''
    try:
        with socket.create_connection(('127.0.0.1', int(endpoint)), timeout=3) as connection:
            connection.sendall(json.dumps(message).encode() + b'\n')
            with connection.makefile('rb') as stream:
                status = int(stream.readline(8))
                return status, stream.read()
    except (ValueError, OSError):
        return 503, b''


CONTROL_PAGE = '''<style>
.remote-view { display:block; width:auto; height:auto; max-width:100%; max-height:75vh;
  margin:12px auto; touch-action:none; user-select:none; -webkit-user-select:none; }
.remote-form {display:flex; align-items:center; gap:12px; flex-wrap:wrap;}
.remote-form input {font:inherit; padding:8px; width:9em;}
</style>
<h1>Control remoto</h1>
<form id="pair" class="remote-form panel connection">
<label for="pin">Código del equipo</label>
<input id="pin" inputmode="numeric" autocomplete="off" maxlength="6" pattern="[0-9]{6}" required>
<button class="theme">Conectar</button></form>
<p id="status" role="status">Activá Control remoto en Configuración → General e ingresá el código de la pantalla.</p>
<img id="screen" class="remote-view" draggable="false" hidden alt="Pantalla táctil de Mulita">
<button id="leave" class="theme" hidden>Desconectar</button>
<script>
(() => {
const pair = document.getElementById('pair'), pin = document.getElementById('pin');
const screen = document.getElementById('screen'), status = document.getElementById('status');
const leave = document.getElementById('leave');
let token = '', active = null, url = '', queue = [], sending = false, lastPoint = null;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function post(action, data={}, key=token) {
  return fetch('/control/' + action, {method:'POST', cache:'no-store', credentials:'omit',
    headers:{'Content-Type':'application/json', 'Authorization':'Bearer ' + key},
    body:JSON.stringify(data)});
}
function reset(text) {
  token = ''; active = null; queue = []; lastPoint = null;
  screen.hidden = leave.hidden = true; pair.hidden = false; status.textContent = text;
  screen.removeAttribute('src'); if (url) URL.revokeObjectURL(url); url = '';
}
async function frames(key) {
  while (token === key) {
    try {
      const r = await post('frame', {}, key);
      if (token !== key) return;
      if (!r.ok) throw Error();
      if (r.status === 200) {
        const next = URL.createObjectURL(await r.blob());
        if (token !== key) { URL.revokeObjectURL(next); return; }
        screen.src = next; if (url) URL.revokeObjectURL(url); url = next;
        screen.hidden = false; status.textContent = '';
      }
    } catch (_) { if (token === key) reset('La sesión terminó. Volvé a habilitarla en el equipo.'); return; }
    await delay(300);
  }
}
pair.onsubmit = async e => {
  e.preventDefault();
  try {
    const r = await post('pair', {code:pin.value});
    if (!r.ok) throw Error();
    token = await r.text(); pin.value = ''; pair.hidden = true; leave.hidden = false;
    status.textContent = 'Conectado. Esperando la pantalla…'; frames(token);
  } catch (_) { status.textContent = 'Comprobá el código y que Control remoto esté activo en el equipo.'; }
};
async function send(data) {
  if (data.kind === 'move' && queue.length && queue[queue.length-1].kind === 'move') queue.pop();
  queue.push(data);
  if (sending) return;
  sending = true;
  const key = token;
  try {
    while (queue.length && token === key) {
      const r = await post('input', queue.shift(), key);
      if (!r.ok) throw Error();
    }
  } catch (_) { if (token === key) { post('end', {}, key).catch(()=>{}); reset('Se interrumpió el control.'); } }
  finally { sending = false; }
}
function point(e) {
  const r = screen.getBoundingClientRect(), clamp = n => Math.max(0,Math.min(1,n));
  return {x:clamp((e.clientX-r.left)/r.width), y:clamp((e.clientY-r.top)/r.height)};
}
screen.oncontextmenu = e => e.preventDefault();
screen.onpointerdown = e => {
  if (!token || active !== null || e.button !== 0) return;
  e.preventDefault(); active = e.pointerId; screen.setPointerCapture(active);
  lastPoint = point(e); send({kind:'down', ...lastPoint});
};
screen.onpointermove = e => {
  if (e.pointerId !== active) return;
  lastPoint = point(e); send({kind:'move', ...lastPoint});
};
screen.onpointerup = e => {
  if (e.pointerId !== active) return;
  active = null; lastPoint = null; send({kind:'up', ...point(e)});
};
function cancel() { if (active !== null) { active=null; lastPoint=null; send({kind:'cancel'}); } }
screen.onpointercancel = screen.onlostpointercapture = cancel;
window.addEventListener('blur', cancel);
setInterval(() => { if (active !== null && lastPoint) send({kind:'move', ...lastPoint}); }, 1000);
leave.onclick = () => { post('end').catch(()=>{}); reset('Sesión cerrada.'); };
window.addEventListener('pagehide', () => {
  if (token) fetch('/control/end',{method:'POST',keepalive:true,credentials:'omit',
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:'{}'}).catch(()=>{});
});
})();
</script>'''
