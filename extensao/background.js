// Quando a aba do escritório abre, cria uma regra só para essa aba: as telas (iframes) dela
// deixam de receber os cabeçalhos que proíbem um site de abrir dentro de outro.
const OFFICE = 'http://127.0.0.1:8765';

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (msg !== 'escritorio-aberto' || !sender.tab || !sender.url || !sender.url.startsWith(OFFICE + '/')) return;
  const tabId = sender.tab.id, id = 1000 + (tabId % 100000);
  // regra principal sozinha: se a do YouTube falhar, as telas continuam funcionando
  chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: [id, id + 500000],
    addRules: [{
      id, priority: 1,
      action: { type: 'modifyHeaders', responseHeaders: [
        { header: 'x-frame-options', operation: 'remove' },
        { header: 'content-security-policy', operation: 'remove' },
      ] },
      condition: { tabIds: [tabId], resourceTypes: ['sub_frame'] },
    }],
  }).then(() => {
    reply(true);
    // página de assistir do YouTube aberta numa tela vai para o player do escritório (yt.html)
    chrome.declarativeNetRequest.updateSessionRules({
      addRules: [{
        id: id + 500000, priority: 2,
        action: { type: 'redirect', redirect: { regexSubstitution: OFFICE + '/yt.html?v=\\1' } },
        condition: { tabIds: [tabId], resourceTypes: ['sub_frame'], regexFilter: '^https://www\\.youtube\\.com/watch\\?v=([A-Za-z0-9_-]{11})' },
      }],
    }).catch(e => console.warn('regra do YouTube:', e && e.message));
  }, e => { console.warn('regra das telas:', e && e.message); reply(false); });
  return true;
});

// Login do Claude dentro das telas: o Chrome só manda para dentro de um iframe de outro site os cookies
// marcados SameSite=None. Os cookies do claude.ai são regravados assim (só os do claude.ai).
const LOGIN_DOMAINS = ['claude.ai'];
const isLoginDomain = d => LOGIN_DOMAINS.some(x => d.replace(/^\./, '') === x || d.endsWith('.' + x));
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

chrome.tabs && chrome.tabs.onRemoved && chrome.tabs.onRemoved.addListener(tabId =>
  chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [1000 + (tabId % 100000)] }));
