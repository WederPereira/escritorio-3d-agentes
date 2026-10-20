// Página do escritório: avisa a extensão e diz à página que as telas podem abrir qualquer site.
// Dentro de uma tela: obedece voltar/avançar/recarregar/volume e conta à página o endereço atual e o Esc.
const OFFICE = 'http://127.0.0.1:8765';

if (window === top) {
  if (location.origin === OFFICE) {
    document.documentElement.dataset.escritorioExt = '1';
    chrome.runtime.sendMessage('escritorio-aberto', ok => {
      document.documentElement.dataset.escritorioRegra = ok ? '1' : '0';
      window.postMessage({ esc: 'ext-pronta', ok: !!ok }, OFFICE);
    });
  }
} else if (window.parent === top) {
  let inOffice = false;
  try { inOffice = location.ancestorOrigins && location.ancestorOrigins[0] === OFFICE; } catch (e) {}
  if (inOffice) {
    const send = m => parent.postMessage(Object.assign({ esc: 'tela' }, m), OFFICE);
    let vol = null;
    const applyVol = () => { if (vol != null) document.querySelectorAll('video,audio').forEach(m => { m.volume = vol; }); };
    addEventListener('message', e => {
      if (e.origin !== OFFICE || !e.data || e.data.esc !== 'cmd') return;
      const { cmd, v } = e.data;
      if (cmd === 'back') history.back();
      else if (cmd === 'forward') history.forward();
      else if (cmd === 'reload') location.reload();
      else if (cmd === 'volume') { vol = Math.max(0, Math.min(1, +v || 0)); applyVol(); }
      else if (cmd === 'replace' && typeof v === 'string' && /^https:\/\//.test(v)) location.replace(v);
      else if (cmd === 'click' && typeof v === 'string') {
        // clica no primeiro elemento que casar com o seletor, esperando até 10 s ele aparecer
        const t0 = Date.now();
        const tryClick = () => { const el = document.querySelector(v); if (el) el.click(); else if (Date.now() - t0 < 10000) setTimeout(tryClick, 300); };
        tryClick();
      }
      else if (cmd === 'css' && typeof v === 'string') {
        // ajustes de visual que o escritório manda para o site da tela (ex.: o claude.ai esconde o título quando está dentro de outra página)
        let st = document.getElementById('escritorio-css');
        if (!st) { st = document.createElement('style'); st.id = 'escritorio-css'; (document.head || document.documentElement).appendChild(st); }
        st.textContent = v;
      }
    });
    // YouTube dentro da tela: em vez de abrir o vídeo numa aba nova (ou na página /watch, que se recusa a abrir aqui),
    // abre o player do YouTube na própria tela
    if (/(^|\.)youtube\.com$/.test(location.hostname)) {
      const ytEmbed = href => {
        const m = /(?:[?&]v=|\/shorts\/)([\w-]{11})/.exec(href || '');
        return m && `https://www.youtube.com/embed/${m[1]}?autoplay=1&rel=1&playsinline=1`;
      };
      addEventListener('click', e => {
        const a = e.target.closest && e.target.closest('a[href]');
        const url = a && /\/(watch|shorts\/)/.test(a.getAttribute('href')) && ytEmbed(a.href);
        // quem abre o player é o escritório (o YouTube recusa com erro 153 se o próprio site abrir o player)
        if (url) { e.preventDefault(); e.stopImmediatePropagation(); send({ video: url }); }
      }, true);
    }
    let last = '';
    setInterval(() => { if (location.href !== last) { last = location.href; send({ url: last, host: location.hostname }); } applyVol(); }, 700);
    addEventListener('keydown', e => { if (e.key === 'Escape') send({ key: 'Escape' }); }, true);
  }
}
