// Página do escritório: avisa a extensão e diz à página que as telas podem abrir qualquer site.
// Dentro de uma tela: obedece voltar/avançar/recarregar/volume e conta à página o endereço atual e o Esc.
const OFFICE = 'http://127.0.0.1:8765';

// As telas conversam com o escritório por dentro da extensão (ponte): alguns sites, como o WhatsApp Web,
// atrapalham a conversa direta entre a página e a tela, e aí os agentes não conseguiam ler nada.
const VERSAO_EXT = chrome.runtime.getManifest().version;
const NOME_TELA = /^(pc\d|tv|spotify)-t\d+$/;

if (window === top) {
  if (location.origin === OFFICE) {
    document.documentElement.dataset.escritorioExt = '1';
    document.documentElement.dataset.escritorioExtVersao = VERSAO_EXT;
    chrome.runtime.sendMessage('escritorio-aberto', ok => {
      document.documentElement.dataset.escritorioRegra = ok ? '1' : '0';
      window.postMessage({ esc: 'ext-pronta', ok: !!ok, versao: VERSAO_EXT, ponte: true }, OFFICE);
    });
    // escritório -> tela: a página pede, a extensão entrega na guia certa
    addEventListener('message', e => {
      if (e.source !== window || !e.data || e.data.esc !== 'ponte-cmd') return;
      chrome.runtime.sendMessage({ tipo: 'cmd', nome: e.data.nome, m: e.data.m });
    });
    // tela -> escritório
    chrome.runtime.onMessage.addListener(msg => {
      if (msg && msg.tipo === 'tela') window.postMessage(Object.assign({}, msg.data, { esc: 'tela', nome: msg.nome }), OFFICE);
    });
  }
} else {
  // o nome da guia vem do escritório (ex.: pc1-t3); lido logo no começo, antes do site mexer nele
  const nome = window.name;
  let inOffice = false, ponte = false, iniciado = false;
  try { inOffice = window.parent === top && location.ancestorOrigins && location.ancestorOrigins[0] === OFFICE; } catch (e) {}
  if (NOME_TELA.test(nome)) chrome.runtime.sendMessage({ tipo: 'sou-tela', nome, host: location.hostname }, ok => { if (ok) { ponte = true; iniciar(); } });
  if (inOffice) iniciar();
  function iniciar() {
    if (iniciado) return; iniciado = true;
    const send = m => {
      if (ponte) { try { chrome.runtime.sendMessage({ tipo: 'tela', nome, data: m }); return; } catch (e) {} }
      parent.postMessage(Object.assign({ esc: 'tela' }, m), OFFICE);
    };
    let vol = null;
    const applyVol = () => { if (vol != null) document.querySelectorAll('video,audio').forEach(m => { m.volume = vol; }); };
    const feitos = new Set();
    const receber = data => {
      if (!data || data.esc !== 'cmd') return;
      if (data.id) { if (feitos.has(data.id)) return; feitos.add(data.id); }
      const { cmd, v } = data;
      if (cmd === 'back') history.back();
      else if (cmd === 'forward') history.forward();
      else if (cmd === 'reload') location.reload();
      else if (cmd === 'volume') { vol = Math.max(0, Math.min(1, +v || 0)); applyVol(); }
      else if (cmd === 'pause') document.querySelectorAll('video,audio').forEach(m => m.pause());
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
      // os agentes usando a tela; a resposta volta com o mesmo id
      else if (['ler', 'clicar', 'rolar', 'digitar', 'perguntar'].includes(cmd) && data.id) {
        Promise.resolve().then(() => agir(cmd, typeof v === 'string' ? v : '', data))
          .catch(err => ({ ok: false, mensagem: String(err && err.message || err) }))
          .then(r => send({ resposta: Object.assign({ id: data.id, url: location.href, titulo: document.title }, r) }));
      }
    };
    addEventListener('message', e => { if (e.origin === OFFICE) receber(e.data); });
    chrome.runtime.onMessage.addListener(msg => { if (msg && msg.tipo === 'cmd' && msg.nome === nome) receber(msg.m); });

    // ---------- leitura e ações dos agentes
    const semAcento = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
    const linhas = s => String(s || '').replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim();
    const visivel = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const ZAP = /(^|\.)web\.whatsapp\.com$/.test(location.hostname);
    // WhatsApp Web: lista de conversas e, se uma estiver aberta, as mensagens dela
    const esperarMs = ms => new Promise(r => setTimeout(r, ms));
    // lista de conversas: o WhatsApp muda o visual de tempos em tempos, então tenta vários jeitos
    function zapLista() {
      const lados = ['#pane-side', '[aria-label="Lista de conversas"]', '[aria-label="Chat list"]', '[aria-label*="conversas" i][role="grid"]', '[aria-label*="chat" i][role="grid"]', '#side'];
      for (const sel of lados) {
        const lado = document.querySelector(sel); if (!lado) continue;
        const itens = [...lado.querySelectorAll('[role="listitem"], [role="row"]')].filter(el => !el.parentElement.closest('[role="listitem"], [role="row"]') && visivel(el) && linhas(el.innerText));
        if (itens.length) return itens;
      }
      // sem marcação: blocos com hora ou dia, fora da conversa aberta
      return [...document.querySelectorAll('div[tabindex], [role="button"]')].filter(el => !el.closest('#main, footer, header') && visivel(el)
        && /\n/.test(el.innerText || '') && /(\d{1,2}:\d{2}|ontem|yesterday|segunda|terça|quarta|quinta|sexta|sábado|domingo|\d{1,2}\/\d{1,2})/i.test(el.innerText || '')
        && el.getBoundingClientRect().height < 110).filter((el, i, a) => !a.some(o => o !== el && o.contains(el)));
    }
    function lerZap() {
      const lista = zapLista().slice(0, 25).map((el, i) => {
        const t = linhas(el.innerText).split('\n').map(x => x.trim()).filter(Boolean);
        return `${i + 1}. ${t[0] || '?'}${t[1] ? ' · ' + t[1] : ''}${t[2] ? ' · ' + t.slice(2).join(' ') : ''}`;
      });
      const main = document.querySelector('#main');
      let aberta = '';
      if (main) {
        const nome = main.querySelector('header span[dir="auto"], header span[title]');
        const msgs = [...main.querySelectorAll('[data-pre-plain-text]')].slice(-40).map(m =>
          `${m.getAttribute('data-pre-plain-text').trim()} ${linhas((m.querySelector('.selectable-text') || m).innerText)}`);
        aberta = `\n\nConversa aberta: ${nome ? linhas(nome.innerText || nome.title) : '(sem nome)'}\n` + (msgs.join('\n') || linhas(main.innerText).slice(-4000));
      }
      if (!lista.length) {
        const qr = document.querySelector('canvas[aria-label*="QR" i], [data-ref] canvas, [data-testid="qrcode"]');
        if (qr) return 'WhatsApp Web: está na tela do QR code (falta conectar o celular).';
        const tudo = linhas(document.body ? document.body.innerText : '');
        if (tudo.length < 40) return 'WhatsApp Web: a página ainda está carregando.';
        return `WhatsApp Web (lido como texto, porque não reconheci a lista):\n${tudo.slice(0, 8000)}${aberta}`;
      }
      return `WhatsApp Web · conversas (na ordem da lista; a 1 é a mais recente):\n${lista.join('\n')}${aberta}`;
    }
    function ler() {
      if (ZAP) return lerZap().slice(0, 12000);
      const texto = linhas(document.body ? document.body.innerText : '').slice(0, 9000);
      const clicaveis = [...new Set([...document.querySelectorAll('a, button, [role="button"], [role="tab"], [role="link"], [role="menuitem"]')]
        .filter(visivel).map(el => linhas(el.innerText || el.getAttribute('aria-label') || el.title).split('\n')[0]).filter(t => t && t.length < 60))].slice(0, 60);
      return `${texto}${clicaveis.length ? '\n\nDá para clicar em: ' + clicaveis.join(' | ') : ''}`;
    }
    // clique "de verdade" (alguns sites, como o WhatsApp, só reagem ao mouse descendo e subindo)
    function clicarEm(el) {
      el.scrollIntoView({ block: 'center' });
      const r = el.getBoundingClientRect(), o = { bubbles: true, cancelable: true, view: window, clientX: r.left + r.width / 2, clientY: r.top + Math.min(r.height / 2, 20) };
      ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(t => el.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t, o)));
    }
    function acharAlvo(alvo) {
      const n = /^#?\s*(\d{1,3})$/.exec(alvo.trim());
      if (n) { // número do item da lista (no WhatsApp, a conversa; fora dele, o item de lista visível)
        const itens = ZAP ? zapLista() : [...document.querySelectorAll('[role="listitem"], [role="row"], [role="option"], li')].filter(visivel);
        return itens[+n[1] - 1] || null;
      }
      const q = semAcento(alvo);
      const cands = [...document.querySelectorAll('a, button, [role="button"], [role="listitem"], [role="row"], [role="tab"], [role="option"], [role="menuitem"], [role="link"], li, label, span[title], div[title], h1, h2, h3, span, div')]
        .filter(visivel)
        .map(el => ({ el, t: semAcento(el.innerText || el.getAttribute('aria-label') || el.title) }))
        .filter(c => c.t && c.t.includes(q));
      if (!cands.length) return null;
      // o mais exato e mais "de dentro"; no WhatsApp, sobe até a linha da conversa
      cands.sort((a, b) => (a.t === q ? 0 : 1) - (b.t === q ? 0 : 1) || a.t.length - b.t.length);
      const el = cands[0].el;
      return (ZAP && el.closest('#pane-side [role="listitem"], #pane-side [role="row"]')) || el.closest('a, button, [role="button"], [role="listitem"], [role="row"], [role="tab"], [role="option"], [role="menuitem"]') || el;
    }
    function rolavel() {
      const els = [...document.querySelectorAll('*')].filter(el => el.scrollHeight > el.clientHeight + 40 && /(auto|scroll)/.test(getComputedStyle(el).overflowY) && visivel(el));
      els.sort((a, b) => b.clientHeight * b.clientWidth - a.clientHeight * a.clientWidth);
      return ZAP && document.querySelector('#main [role="application"], #main .copyable-area > div') || els[0] || document.scrollingElement;
    }
    // ---------- conversar com uma IA aberta na tela (claude.ai, ChatGPT, Gemini...): escreve, envia e espera a resposta
    const CAIXA = 'div.ProseMirror[contenteditable="true"], [contenteditable="true"][role="textbox"], #prompt-textarea, rich-textarea [contenteditable="true"], textarea, [contenteditable="true"]';
    const RESPOSTAS = '[data-is-streaming], .font-claude-response, .font-claude-message, [data-message-author-role="assistant"], model-response, message-content';
    const botaoCom = re => [...document.querySelectorAll('button, [role="button"]')].filter(visivel).find(b => re.test((b.getAttribute('aria-label') || '') + ' ' + (b.getAttribute('data-testid') || '') + ' ' + (b.title || '')));
    const respondendo = () => !!document.querySelector('[data-is-streaming="true"]') || !!botaoCom(/stop|parar|interromper/i);
    const ultimaResposta = () => { const r = [...document.querySelectorAll(RESPOSTAS)].filter(el => !el.parentElement.closest(RESPOSTAS)); return r.length ? linhas(r[r.length - 1].innerText) : ''; };
    function escrever(el, texto) {
      el.focus();
      if (el.isContentEditable) {
        document.execCommand('selectAll', false, null); document.execCommand('delete', false, null);
        if (!document.execCommand('insertText', false, texto)) el.textContent = texto;
      } else {
        const set = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set; set.call(el, texto);
        el.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }
    const apertarEnter = el => ['keydown', 'keypress', 'keyup'].forEach(t => el.dispatchEvent(new KeyboardEvent(t, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true })));
    async function perguntar(texto, ms) {
      if (ZAP) return { ok: false, mensagem: 'perguntar é para sites de IA (claude.ai, ChatGPT...); no WhatsApp os agentes só leem' };
      const caixa = [...document.querySelectorAll(CAIXA)].filter(visivel).pop();
      if (!caixa) return { ok: false, mensagem: 'não achei a caixa de mensagem desta página (ela está logada e com um chat aberto?)', texto: ler() };
      const antes = document.querySelectorAll(RESPOSTAS).length, textoAntes = ultimaResposta();
      escrever(caixa, texto);
      await esperarMs(600);
      const enviar = botaoCom(/send|enviar|submit/i);
      if (enviar && !enviar.disabled) clicarEm(enviar); else apertarEnter(caixa);
      // espera começar e terminar de responder (o texto parar de mudar por uns segundos)
      const fim = Date.now() + ms;
      let ultimo = '', parado = 0, comecou = false;
      while (Date.now() < fim) {
        await esperarMs(1500);
        const agora = ultimaResposta(), novos = document.querySelectorAll(RESPOSTAS).length > antes;
        if (novos || (agora && agora !== textoAntes)) comecou = true;
        if (comecou && !respondendo() && agora && agora === ultimo) { if (++parado >= 2) break; } else parado = 0;
        ultimo = agora;
      }
      if (!comecou) return { ok: false, mensagem: 'escrevi e enviei, mas a resposta não começou (veja se a página pediu login ou se o envio funcionou)', texto: ler() };
      const resp = ultimaResposta();
      const pede = [...document.querySelectorAll('button')].filter(visivel).map(b => linhas(b.innerText)).filter(t => /^(allow|permitir|aprovar|approve|continuar|continue)/i.test(t));
      const ainda = respondendo() || parado < 2;
      return { ok: true, mensagem: ainda ? 'a IA ainda está respondendo: espere um pouco e leia de novo' : 'a IA terminou de responder',
               texto: `Resposta da IA${ainda ? ' (até agora)' : ''}:\n${resp.slice(0, 11000)}${pede.length ? '\n\nA página está pedindo: ' + pede.join(' | ') + ' (clique só se o Wes autorizou)' : ''}` };
    }
    function agir(cmd, alvo, data) {
      if (cmd === 'ler') return { ok: true, texto: ler() };
      if (cmd === 'perguntar') return perguntar(alvo, Math.min(Math.max(+(data && data.ms) || 120000, 10000), 280000));
      if (cmd === 'clicar') {
        const el = acharAlvo(alvo);
        if (!el) return { ok: false, mensagem: `não achei "${alvo}" na tela`, texto: ler() };
        clicarEm(el);
        return { ok: true, mensagem: `cliquei em "${linhas(el.innerText || el.title || alvo).split('\n')[0].slice(0, 80)}"` };
      }
      if (cmd === 'rolar') {
        const el = rolavel(), passo = Math.round((el.clientHeight || innerHeight) * 0.8) * (/cima|up|topo/.test(semAcento(alvo)) ? -1 : 1);
        el.scrollBy({ top: passo });
        return { ok: true, mensagem: `rolei para ${passo < 0 ? 'cima' : 'baixo'}` };
      }
      if (cmd === 'digitar') {
        // regra do escritório: no WhatsApp os agentes só leem, nunca escrevem para cliente
        if (ZAP) return { ok: false, mensagem: 'no WhatsApp os agentes só leem: digitar está bloqueado' };
        const el = document.activeElement && /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName) ? document.activeElement
          : [...document.querySelectorAll('input[type="text"], input[type="search"], input:not([type]), textarea, [contenteditable="true"]')].find(visivel);
        if (!el) return { ok: false, mensagem: 'não achei onde digitar nesta tela' };
        el.focus();
        if (el.isContentEditable) document.execCommand('insertText', false, alvo);
        else { const set = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set; set.call(el, alvo); el.dispatchEvent(new Event('input', { bubbles: true })); }
        return { ok: true, mensagem: `digitei "${alvo.slice(0, 80)}" (sem enviar)` };
      }
      return { ok: false, mensagem: 'ação desconhecida' };
    }
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
    // link que abriria uma guia nova (target=_blank, Ctrl/⌘+clique ou botão do meio): vira uma guia no próprio PC.
    // window.open fica como está, porque os logins (Google, etc.) abrem em janelinha e precisam dela.
    const newTabLink = (e, background) => {
      const a = e.target.closest && e.target.closest('a[href]');
      if (!a || !/^https?:$/.test(a.protocol)) return;
      e.preventDefault(); e.stopImmediatePropagation();
      send({ newTab: a.href, background });
    };
    addEventListener('click', e => {
      if (e.button !== 0) return;
      const a = e.target.closest && e.target.closest('a[href]');
      if (a && (a.target === '_blank' || e.ctrlKey || e.metaKey)) newTabLink(e, e.ctrlKey || e.metaKey);
    }, true);
    addEventListener('auxclick', e => { if (e.button === 1) newTabLink(e, true); }, true);
    let last = '', lastTitle = '', tocou = false;
    // conta ao escritório quando a página começa ou para de tocar som (para a mesa de som e o alto-falante na guia)
    const tocando = () => [...document.querySelectorAll('video,audio')].some(m => !m.paused && !m.ended && m.readyState > 2);
    setInterval(() => {
      const t = tocando(); if (t !== tocou) { tocou = t; send({ tocando: t }); }
      if (location.href !== last) { last = location.href; lastTitle = document.title; send({ url: last, host: location.hostname, title: lastTitle }); }
      else if (document.title !== lastTitle) { lastTitle = document.title; send({ title: lastTitle }); }
      applyVol();
    }, 700);
    addEventListener('keydown', e => { if (e.key === 'Escape') send({ key: 'Escape' }); }, true);
  }
}
