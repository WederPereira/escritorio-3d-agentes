// App do Escritório 3D: um navegador próprio que deixa qualquer site (YouTube, Agenda, Claude...) abrir
// dentro dos monitores e da TV da cena. Os sites bloqueiam isso no Chrome com X-Frame-Options e
// frame-ancestors; aqui essas proteções são retiradas só dentro deste app.
const { app, BrowserWindow, session, ipcMain, webFrameMain, components } = require('electron');
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const PORT = 8765;
const PAGE = `http://127.0.0.1:${PORT}/escritorio-3d.html`;
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml' };

// servidor local em 127.0.0.1 (o Spotify só aceita login nesse endereço); se já houver um rodando, usa ele
function serve() {
  return new Promise(resolve => {
    const srv = http.createServer((req, res) => {
      let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
      if (p === '/') p = '/escritorio-3d.html';
      const file = path.normalize(path.join(ROOT, p));
      if (!file.startsWith(ROOT) || file.includes(`${path.sep}node_modules${path.sep}`)) { res.writeHead(403); return res.end(); }
      fs.readFile(file, (err, data) => {
        if (err) { res.writeHead(404); return res.end(); }
        res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
        res.end(data);
      });
    });
    srv.on('error', () => resolve());
    srv.listen(PORT, '127.0.0.1', () => resolve());
  });
}

// sem a marca "Electron" no navegador, os sites tratam o app como um Chrome normal
app.userAgentFallback = app.userAgentFallback.replace(/ Electron\/\S+/, '').replace(/ escritorio-3d-agentes\/\S+/, '');

let win = null;
function childFrame(name) {
  return win && win.webContents.mainFrame.frames.find(f => f.name === name);
}

app.whenReady().then(async () => {
  if (components && components.whenReady) { try { await components.whenReady(); } catch (e) { console.warn('Widevine não carregou:', e); } }
  await serve();

  session.defaultSession.webRequest.onHeadersReceived((details, cb) => {
    const h = details.responseHeaders || {};
    for (const k of Object.keys(h)) {
      const l = k.toLowerCase();
      if (l === 'x-frame-options') delete h[k];
      if (l === 'content-security-policy' || l === 'content-security-policy-report-only') h[k] = h[k].map(v => v.replace(/frame-ancestors[^;]*;?/gi, ''));
      if (l === 'cross-origin-opener-policy' || l === 'cross-origin-embedder-policy') delete h[k];
    }
    cb({ responseHeaders: h });
  });
  session.defaultSession.setPermissionRequestHandler((wc, perm, cb) => cb(['fullscreen', 'pointerLock', 'media', 'clipboard-sanitized-write', 'notifications'].includes(perm)));

  win = new BrowserWindow({
    width: 1600, height: 950, backgroundColor: '#14161b', title: 'Escritório dos Agentes', autoHideMenuBar: true,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, backgroundThrottling: false },
  });
  win.maximize();

  // logins (Google, Spotify) abrem numa janela própria do app, com a mesma sessão
  win.webContents.setWindowOpenHandler(() => ({ action: 'allow', overrideBrowserWindowOptions: { autoHideMenuBar: true, width: 900, height: 760 } }));

  // avisa a cena qual endereço cada tela está mostrando (inclusive navegação interna do YouTube)
  const report = (url, isMain, pid, rid) => {
    if (isMain) return;
    const fr = webFrameMain.fromId(pid, rid);
    if (fr && fr.name && fr.parent === win.webContents.mainFrame) win.webContents.send('frame-url', fr.name, url);
  };
  win.webContents.on('did-frame-navigate', (e, url, code, status, isMain, pid, rid) => report(url, isMain, pid, rid));
  win.webContents.on('did-navigate-in-page', (e, url, isMain, pid, rid) => report(url, isMain, pid, rid));

  // Esc dentro de um site (que fica com o teclado) também levanta da tela
  win.webContents.on('before-input-event', (e, input) => {
    if (input.type === 'keyDown' && input.key === 'Escape') win.webContents.send('esc');
  });

  win.loadURL(PAGE);
});

ipcMain.handle('nav', (e, name, cmd) => {
  const fr = childFrame(name); if (!fr) return false;
  const js = { back: 'history.back()', forward: 'history.forward()', reload: 'location.reload()' }[cmd];
  if (js) fr.executeJavaScript(js).catch(() => {});
  return true;
});
// volume da TV e da caixa de som pela distância
ipcMain.handle('volume', (e, name, v) => {
  const fr = childFrame(name); if (!fr) return false;
  const vol = Math.max(0, Math.min(1, Number(v) || 0));
  fr.executeJavaScript(`document.querySelectorAll('video,audio').forEach(m => { m.volume = ${vol}; })`).catch(() => {});
  return true;
});

app.on('window-all-closed', () => app.quit());
