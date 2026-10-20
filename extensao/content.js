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
    });
    let last = '';
    setInterval(() => { if (location.href !== last) { last = location.href; send({ url: last }); } applyVol(); }, 700);
    addEventListener('keydown', e => { if (e.key === 'Escape') send({ key: 'Escape' }); }, true);
  }
}
