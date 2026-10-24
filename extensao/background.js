// Quando a aba do escritório abre, cria uma regra só para essa aba: as telas (iframes) dela
// deixam de receber os cabeçalhos que proíbem um site de abrir dentro de outro.
const OFFICE = 'http://127.0.0.1:8765';
// sites da Meta: o servidor recusa ("Sorry, something went wrong") quando o Chrome avisa que a página vai abrir dentro de outra
const META_DOMAINS = ['whatsapp.com', 'facebook.com', 'messenger.com', 'instagram.com', 'threads.net', 'threads.com'];
const ruleIds = tabId => { const id = 1000 + (tabId % 100000); return [id, id + 250000, id + 500000, id + 750000]; };
const SEC_FETCH_DOCUMENTO = [
  { header: 'sec-fetch-dest', operation: 'set', value: 'document' },
  { header: 'sec-fetch-mode', operation: 'set', value: 'navigate' },
  { header: 'sec-fetch-site', operation: 'set', value: 'none' },
  { header: 'sec-fetch-user', operation: 'set', value: '?1' },
];
// sites que já abriram numa tela do escritório (guardado enquanto o Chrome estiver aberto): para eles, a tela se
// comporta como uma aba comum também quando se navega dentro do site, e os logins funcionam dentro da tela
const dominiosTelas = async () => ((await chrome.storage.session.get('dominiosTelas')).dominiosTelas || []);
const regraSites = (tabId, dominios) => ({
  id: 1000 + (tabId % 100000) + 250000, priority: 1,
  action: { type: 'modifyHeaders', requestHeaders: SEC_FETCH_DOCUMENTO },
  condition: { tabIds: [tabId], resourceTypes: ['sub_frame'], requestDomains: [...new Set(META_DOMAINS.concat(dominios))] },
});

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (msg !== 'escritorio-aberto' || !sender.tab || !sender.url || !sender.url.startsWith(OFFICE + '/')) return;
  const tabId = sender.tab.id, id = 1000 + (tabId % 100000);
  dominiosTelas().then(dominios => chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: ruleIds(tabId),
    addRules: [regraSites(tabId, dominios), {
      // o que o escritório abre direto numa tela: pedido como uma aba comum, com o endereço digitado na barra
      // (muitos sites recusam ou mostram erro quando percebem que estão dentro de outra página)
      id: id + 750000, priority: 1,
      action: { type: 'modifyHeaders', requestHeaders: SEC_FETCH_DOCUMENTO },
      condition: { tabIds: [tabId], resourceTypes: ['sub_frame'], initiatorDomains: ['127.0.0.1'] },
    }, {
      id, priority: 1,
      action: { type: 'modifyHeaders', responseHeaders: [
        { header: 'x-frame-options', operation: 'remove' },
        { header: 'content-security-policy', operation: 'remove' },
      ] },
      condition: { tabIds: [tabId], resourceTypes: ['sub_frame'] },
    }, {
      // página de assistir do YouTube aberta numa tela vira o player do YouTube (que aceita abrir aqui e tem tela cheia).
      // A expressão precisa ser simples: com {11} ela passa do limite de memória do Chrome, e aí nenhuma regra desta lista entra.
      id: id + 500000, priority: 2,
      action: { type: 'redirect', redirect: { regexSubstitution: OFFICE + '/yt.html?v=\\3' } },
      condition: { tabIds: [tabId], resourceTypes: ['sub_frame'], regexFilter: '^https://(www\\.|m\\.)?youtube\\.com/watch\\?(.*&)?v=([\\w-]+).*' },
    }],
  })).then(() => reply(true), () => reply(false));
  return true;
});

// Login do Claude e do Spotify dentro das telas: o Chrome só manda para dentro de um iframe de outro site os cookies
// marcados SameSite=None. Os cookies desses sites são regravados assim (só os deles).
const LOGIN_DOMAINS = ['claude.ai', 'spotify.com'];
let loginExtras = [];
chrome.storage.session.get('dominiosTelas').then(r => { loginExtras = r.dominiosTelas || []; }).catch(() => {});
const isLoginDomain = d => LOGIN_DOMAINS.concat(loginExtras).some(x => d.replace(/^\./, '') === x || d.endsWith('.' + x));
function fixCookie(c) {
  if (!isLoginDomain(c.domain) || c.sameSite === 'no_restriction') return;
  const host = c.domain.replace(/^\./, '');
  const nc = { url: `https://${host}${c.path}`, name: c.name, value: c.value, path: c.path, secure: true, httpOnly: c.httpOnly, sameSite: 'no_restriction', storeId: c.storeId };
  if (!c.hostOnly) nc.domain = c.domain;
  if (!c.session && c.expirationDate) nc.expirationDate = c.expirationDate;
  chrome.cookies.set(nc).catch(() => {});
}
const fixAll = () => LOGIN_DOMAINS.forEach(domain => chrome.cookies.getAll({ domain }).then(list => list.forEach(fixCookie)));
chrome.cookies.onChanged.addListener(({ removed, cookie }) => { if (!removed) fixCookie(cookie); });
chrome.runtime.onInstalled.addListener(fixAll);
chrome.runtime.onStartup.addListener(fixAll);
chrome.runtime.onMessage.addListener(msg => { if (msg === 'escritorio-aberto') fixAll(); });

// um site novo numa tela: entra na regra da aba e tem os logins liberados dentro das telas
async function lembrarDominio(tabId, host) {
  const d = String(host).replace(/^www\./, '').toLowerCase();
  if (!d || d === '127.0.0.1' || d === 'localhost') return;
  const dominios = await dominiosTelas();
  if (dominios.includes(d)) return;
  dominios.push(d); loginExtras = dominios;
  await chrome.storage.session.set({ dominiosTelas: dominios.slice(-200) });
  chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [1000 + (tabId % 100000) + 250000], addRules: [regraSites(tabId, dominios)] }).catch(() => {});
  chrome.cookies.getAll({ domain: d }).then(list => list.forEach(fixCookie)).catch(() => {});
}

// Ponte entre o escritório e as telas: cada guia de tela (iframe pc1-t3, tv-t2...) se apresenta, e as mensagens
// passam por aqui. Só vale dentro da aba do escritório.
const naAbaDoEscritorio = sender => !!(sender.tab && sender.tab.url && sender.tab.url.startsWith(OFFICE + '/'));
chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (!msg || typeof msg !== 'object') return;
  if (msg.tipo === 'sou-tela') {
    const ok = naAbaDoEscritorio(sender) && sender.frameId !== 0;
    reply(ok);
    if (ok && msg.host) lembrarDominio(sender.tab.id, msg.host);
    return;
  }
  if (!naAbaDoEscritorio(sender)) return;
  // escritório -> tela: entrega para os quadros da aba; só a guia com esse nome obedece
  if (msg.tipo === 'cmd' && sender.frameId === 0) chrome.tabs.sendMessage(sender.tab.id, { tipo: 'cmd', nome: msg.nome, m: msg.m }).catch(() => {});
  // tela -> escritório: entrega só para a página do escritório (quadro principal)
  if (msg.tipo === 'tela' && sender.frameId !== 0) chrome.tabs.sendMessage(sender.tab.id, { tipo: 'tela', nome: msg.nome, data: msg.data }, { frameId: 0 }).catch(() => {});
});

chrome.tabs && chrome.tabs.onRemoved && chrome.tabs.onRemoved.addListener(tabId =>
  chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: ruleIds(tabId) }));
