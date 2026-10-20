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

// O Google recusa login e mostra "não sou um robô" quando o navegador não parece um Chrome comum.
// Por isso o app se apresenta igual ao Chrome: texto do navegador sem "Electron" e as mesmas "marcas"
// (userAgentData / Sec-CH-UA) que o Chrome envia, em todas as telas, janelas e workers.
app.userAgentFallback = app.userAgentFallback.replace(/ Electron\/\S+/, '').replace(/ escritorio-3d-agentes\/\S+/, '');
const CHROME_FULL = (process.versions.chrome || '150.0.0.0');
const CHROME_MAJOR = CHROME_FULL.split('.')[0];
const UA_OVERRIDE = {
  userAgent: app.userAgentFallback,
  acceptLanguage: 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
  platform: 'Win32',
  userAgentMetadata: {
    brands: [{ brand: 'Google Chrome', version: CHROME_MAJOR }, { brand: 'Chromium', version: CHROME_MAJOR }, { brand: 'Not;A=Brand', version: '8' }],
    fullVersionList: [{ brand: 'Google Chrome', version: CHROME_FULL }, { brand: 'Chromium', version: CHROME_FULL }, { brand: 'Not;A=Brand', version: '8.0.0.0' }],
    fullVersion: CHROME_FULL, platform: 'Windows', platformVersion: '15.0.0', architecture: 'x86', model: '', mobile: false, bitness: '64', wow64: false,
  },
};
function disguise(wc) {
  const dbg = wc.debugger;
  try { dbg.attach('1.3'); } catch (e) { return; }
  const apply = sessionId => {
    dbg.sendCommand('Emulation.setUserAgentOverride', UA_OVERRIDE, sessionId).catch(() => {})
      .then(() => dbg.sendCommand('Runtime.runIfWaitingForDebugger', {}, sessionId).catch(() => {}));
    dbg.sendCommand('Target.setAutoAttach', { autoAttach: true, waitForDebuggerOnStart: true, flatten: true }, sessionId).catch(() => {});
  };
  dbg.on('message', (e, method, params) => { if (method === 'Target.attachedToTarget') apply(params.sessionId); });
  dbg.sendCommand('Emulation.setUserAgentOverride', UA_OVERRIDE).catch(() => {});
  dbg.sendCommand('Target.setAutoAttach', { autoAttach: true, waitForDebuggerOnStart: true, flatten: true }).catch(() => {});
}
app.on('web-contents-created', (e, wc) => disguise(wc));

let win = null;
function childFrame(name) {
  return win && win.webContents.mainFrame.frames.find(f => f.name === name);
}

app.whenReady().then(async () => {
  if (components && components.whenReady) {
    try { await components.whenReady(); } catch (e) { console.warn('Widevine não carregou:', e); }
    console.log('componentes:', JSON.stringify(components.status && components.status()));
  }
  await serve();

  session.defaultSession.webRequest.onHeadersReceived((details, cb) => {
    const h = details.responseHeaders || {};
    for (const k of Object.keys(h)) {
      const l = k.toLowerCase();
      if (l === 'x-frame-options') delete h[k];
      if (l === 'content-security-policy' || l === 'content-security-policy-report-only') h[k] = h[k].map(v => v.replace(/frame-ancestors[^;]*;?/gi, ''));
      if (l === 'cross-origin-opener-policy' || l === 'cross-origin-embedder-policy') delete h[k];
      // dentro das telas todo site é "de outro site"; cookies Lax/Strict não seriam enviados e o login não ficaria salvo
      if (l === 'set-cookie' && details.url.startsWith('https://')) {
        h[k] = h[k].map(c => /;\s*samesite=none/i.test(c) ? c : c.replace(/;\s*samesite=(lax|strict)/ig, '') + '; SameSite=None' + (/;\s*secure/i.test(c) ? '' : '; Secure'));
      }
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

  // autoteste (ESCRITORIO_TESTE=1): abre um vídeo na TV, espera e salva foto + estado em app\teste-*.png/log.txt
  const testeArg = process.argv.find(a => a.startsWith('--teste='));
  if (testeArg) win.webContents.once('dom-ready', () => setTimeout(async () => {
    const step = testeArg.split('=')[1];
    await win.webContents.executeJavaScript(`(()=>{ const f=focusables.find(f=>f.key==='tv'); focusOn(f); setTimeout(()=>{ f.el.querySelector('iframe').src='https://www.youtube.com/watch?v=lTRiuFIWV54'; }, 1200); return 1; })()`).catch(e => log('teste js', e.message));
    setTimeout(async () => {
      const fr = childFrame('tv');
      const alive = fr ? await Promise.race([fr.executeJavaScript('location.href + " | " + document.title + " | video:" + !!document.querySelector("video")'), new Promise(r => setTimeout(() => r('SEM RESPOSTA'), 4000))]) : 'sem frame';
      log('teste', step, 'tv frame:', alive);
      const img = await win.webContents.capturePage();
      fs.writeFileSync(path.join(__dirname, `teste-${step}.png`), img.toPNG());
      if (process.argv.includes('--teste-fs') && fr) {
        await fr.executeJavaScript('document.querySelector(".ytp-fullscreen-button") && document.querySelector(".ytp-fullscreen-button").click()', true).catch(() => {});
        setTimeout(async () => { const i2 = await win.webContents.capturePage(); fs.writeFileSync(path.join(__dirname, `teste-${step}-fs.png`), i2.toPNG()); log('teste fs feito'); }, 3000);
      }
    }, 14000);
  }, 6000));
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

// registro de travamentos das telas, para diagnóstico (app\log.txt)
const LOG = path.join(__dirname, 'log.txt');
const log = (...a) => { try { fs.appendFileSync(LOG, new Date().toISOString() + ' ' + a.map(x => typeof x === 'string' ? x : JSON.stringify(x)).join(' ') + '\n'); } catch (e) {} };
app.on('render-process-gone', (e, wc, d) => log('render-process-gone', wc.getURL(), d));
app.on('child-process-gone', (e, d) => log('child-process-gone', d));

app.on('window-all-closed', () => app.quit());
