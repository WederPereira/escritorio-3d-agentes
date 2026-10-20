// Quando a aba do escritório abre, cria uma regra só para essa aba: as telas (iframes) dela
// deixam de receber os cabeçalhos que proíbem um site de abrir dentro de outro.
const OFFICE = 'http://127.0.0.1:8765';

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (msg !== 'escritorio-aberto' || !sender.tab || !sender.url || !sender.url.startsWith(OFFICE + '/')) return;
  const tabId = sender.tab.id, id = 1000 + (tabId % 100000);
  chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: [id],
    addRules: [{
      id, priority: 1,
      action: { type: 'modifyHeaders', responseHeaders: [
        { header: 'x-frame-options', operation: 'remove' },
        { header: 'content-security-policy', operation: 'remove' },
      ] },
      condition: { tabIds: [tabId], resourceTypes: ['sub_frame'] },
    }],
  }).then(() => reply(true), () => reply(false));
  return true;
});

chrome.tabs && chrome.tabs.onRemoved && chrome.tabs.onRemoved.addListener(tabId =>
  chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [1000 + (tabId % 100000)] }));
