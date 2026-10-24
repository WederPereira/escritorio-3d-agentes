# Gera os fluxos do n8n dos agentes do escritório (pasta n8n/), prontos para importar.
#   python tools/gerar-fluxos-n8n.py
#
# escritorio-central.json  guarda o estado de todos os agentes e responde ao escritório 3D
# agente-fabio.json        Fábio · Gestor: responde e distribui tarefas para a equipe
# agente-ana.json          Ana · Comercial: lê o WhatsApp comercial (Evolution ou a tela do WhatsApp Web) e sugere respostas e follow-ups
# agente-carla.json        Carla · Conteúdo e vídeos: roteiros, legendas e vídeos no Abekyo (Remotion)
#
# Protocolo (o escritório e os agentes falam só por webhooks):
#   GET  /webhook/escritorio/estado       -> { ativos, agentes, conversas, eventos, tarefas, mural, telas, comandos }
#   POST /webhook/escritorio/evento       <- { agente, status, tarefa, resultado, mensagem: {de, texto}, evento }
#   POST /webhook/escritorio/<agente>     <- { texto, de }   (pedido para o agente; responde na hora e trabalha depois)
#   POST /webhook/escritorio/mapa         <- { mapa }        (o escritório conta o que está aberto em cada tela)
#   GET  /webhook/escritorio/telas        -> mapa das telas  (ferramenta ver_telas dos agentes)
#   POST /webhook/escritorio/tela         <- { agente, tela, acao, alvo } -> resultado  (ferramenta usar_tela: o escritório faz e responde)
#   POST /webhook/escritorio/resposta     <- { ref, resultado }  (o escritório devolve o resultado de um comando)
import json, os, re, uuid

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'n8n')
# Versão dos agentes: suba a cada mudança nos fluxos. Vai para o Central (o escritório confere) e para n8n/versao.txt
# (o abrir-escritorio.bat compara com o que está instalado no n8n e reinstala sozinho se estiver diferente).
VERSAO = '2026.10.24-painel'
N8N_INTERNO = 'http://localhost:5678'  # endereço do n8n visto de dentro dele mesmo
GEMINI_MODEL = 'models/gemini-2.5-flash'
# Cérebro dos agentes: o Ollama deste PC (o instalador escolhe o modelo que você já tem e ajusta a credencial).
# A memória (numCtx) precisa ser grande: o pedido leva o conteúdo das telas, e o padrão do Ollama (2048) cortaria tudo.
# Lista de cérebros, do preferido para o reserva: se um falhar ou estourar o limite, o agente troca sozinho para o próximo.
# Os modelos "-cloud" rodam na nuvem do Ollama (rápidos e fortes); os outros rodam neste PC. O instalador põe aqui os que você tem.
CEREBROS = ['gpt-oss:120b-cloud', 'deepseek-v3.1:671b-cloud', 'qwen3-coder:480b-cloud', 'gpt-oss:20b-cloud', 'qwen2.5:7b']
OLLAMA_OPCOES = {'temperature': 0.4, 'numCtx': 16384, 'keepAlive': '30m'}
TEMPO_MAXIMO = 900  # segundos: a tarefa que passar disso é cancelada (o Fábio avisa), em vez de ficar carregando para sempre
ABEKYO_N8N = 'http://localhost:3000'   # editor de vídeo Abekyo visto de dentro do n8n (o instalador ajusta)
ABEKYO_TELA = 'http://localhost:3000'  # o mesmo editor visto do Chrome do escritório
CORS = {'entries': [{'name': 'Access-Control-Allow-Origin', 'value': '*'}, {'name': 'Cache-Control', 'value': 'no-store'}]}

EQUIPE = '''- ana · Comercial (ATIVA): lê as conversas do WhatsApp comercial do Cantinho, diz quem está esperando resposta e quem está no ponto de follow-up da régua R1–R5, e prepara as mensagens; o Wes aprova e envia com um clique no chat dela.
- bruno · Leads (ainda sem função): vai vigiar a planilha de leads do tráfego pago.
- carla · Conteúdo e vídeos (ATIVA): escreve carrosséis, roteiros e legendas, cria imagens, e monta e renderiza vídeos no editor Abekyo (Remotion), que fica aberto no PC dela.
- davi · Agenda (ainda sem função): vai resumir e organizar a agenda do Google.
- eva · Relatórios (ainda sem função): vai fazer os relatórios diário e semanal.

Todos da equipe (você também) enxergam e usam as telas do escritório com as ferramentas ver_telas e usar_tela.
Cada um tem o seu computador na mesa: Ana = PC 1 (pc0), Bruno = PC 2 (pc1), Carla = PC 3 (pc2), Davi = PC 4 (pc3), Eva = PC 5 (pc4), Fábio = PC 6 (pc5).'''

TELAS_REGRAS = '''Como você trabalha:
- Seja proativa(o): faça o trabalho em vez de perguntar "quer que eu faça?". Se o próximo passo é óbvio (ler, abrir, clicar, perguntar ao Claude), faça já. Pergunte só quando faltar uma informação que só o Wes tem.
- Quando o Wes ensinar um jeito de trabalhar ("a partir de agora", "sempre", "nunca mais", "lembre que", "da próxima vez"), guarde com a ferramenta lembrar e siga daí em diante. O que já foi guardado aparece em "Instruções permanentes do Wes" e vale mais que o seu jeito padrão.
- Em tarefa com várias etapas (usar telas, perguntar ao Claude, criar imagens), mande logo no começo um recado curto com avisar_wes dizendo o que vai fazer, e outro a cada descoberta importante. Assim o Wes acompanha. Não use avisar_wes para a resposta final.
- Se uma ação falhar duas vezes do mesmo jeito, ou disser que está bloqueada ou não autorizada, não repita: pare e explique o que tentou e o que aconteceu.
- Formato da resposta: frases curtas, um assunto por parágrafo (deixe uma linha em branco entre eles), listas com "-" uma por linha e **negrito** só no essencial (nomes, títulos). Não use tabelas.

Você trabalha usando os computadores do escritório:
- Use as telas só quando o pedido precisa delas. Cumprimento ("oi", "bom dia"), conversa ou pergunta que você já sabe responder: responda direto, sem ferramenta.
- O escritório 3D tem telas que são navegadores de verdade: os PCs (pc0 a pc5, chamados de "PC 1" a "PC 6"), a TV (tv) e o Spotify (spotify). Cada tela pode ter várias guias.
- "Telas agora" mostra o que está aberto em cada tela E o conteúdo dela, lido há poucos segundos. Pergunta sobre o que tem numa tela (um vídeo no YouTube, uma conversa no WhatsApp, uma planilha): responda direto com esse conteúdo.
- Para ver de novo, use a ferramenta ver_telas.
- Para usar uma tela, use a ferramenta usar_tela com:
  - tela: pc0…pc5, tv, spotify, "PC 2", ou o nome do site (ex.: "whatsapp" acha a tela que está com o WhatsApp aberto);
  - acao: ler (lê o que está na tela), clicar (clica no texto ou no número do item da lista em alvo), rolar (alvo: baixo ou cima), abrir (alvo: endereço, abre numa guia nova), guia (alvo: número da guia), voltar, digitar (alvo: texto; nunca no WhatsApp), perguntar (alvo: o pedido completo; escreve na IA aberta na tela, como o Claude, envia e espera a resposta), esperar (alvo: segundos, até 90; depois lê a tela);
  - alvo: o que a ação precisa.
- Seu computador é o da sua mesa: use tela "meu pc".
- Para fazer uma tarefa no Claude (claude.ai): no "meu pc", se o Claude ainda não estiver aberto, use abrir com alvo https://claude.ai/new; depois perguntar com alvo = o pedido completo e claro (o contexto todo, porque o Claude não vê esta conversa). A ferramenta espera o Claude terminar (até ~2 min) e devolve a resposta. Se vier "ainda está respondendo", use esperar e depois ler. No fim, conte ao Wes o que pediu ao Claude, o que ele respondeu e o que fez (resuma, e copie o essencial, como textos prontos e listas).
- Depois de clicar, rolar ou abrir, a ferramenta já devolve a tela lida. Leia antes de responder: não invente o que está na tela.
- A resposta final é sempre sua, em frases: nunca devolva só o texto da ferramenta. Se a tela não respondeu, diga qual tela, o que tentou e o que o Wes pode fazer (ex.: abrir o escritório, recarregar a guia).
- Nunca diga que não consegue ver ou acessar algo sem antes conferir "Telas agora" e tentar usar_tela. Se no histórico você (ou alguém) disse que não conseguia, ignore: tente de novo agora, pelas telas.
- Só se "Telas agora" disser que o escritório está fechado, explique que precisa do escritório aberto no Chrome com a extensão.
- No WhatsApp você só lê. Nunca digite nem envie mensagem: quem envia para os clientes é a Mari (ou o Wes). Deixe a mensagem pronta para copiar.'''


def nid():
    return str(uuid.uuid4())


class Flow:
    def __init__(self, name, wid):
        # número fixo: importar de novo atualiza o fluxo em vez de criar outro igual
        self.name, self.wid, self.nodes, self.conn, self.x = name, wid, [], {}, 0

    def add(self, name, type_, version, params, pos, **extra):
        n = {'parameters': params, 'id': nid(), 'name': name, 'type': type_, 'typeVersion': version, 'position': pos}
        n.update(extra)
        self.nodes.append(n)
        return name

    def link(self, a, b, out=0, kind='main'):
        outs = self.conn.setdefault(a, {}).setdefault(kind, [])
        while len(outs) <= out:
            outs.append([])
        outs[out].append({'node': b, 'type': kind, 'index': 0})

    def chain(self, *names):
        for a, b in zip(names, names[1:]):
            self.link(a, b)

    def save(self, file):
        for n in self.nodes:
            if n['type'] == 'n8n-nodes-base.code':
                n['parameters']['jsCode'] = n['parameters']['jsCode'].replace('__VERSAO__', VERSAO)
        data = {'id': self.wid, 'name': self.name, 'nodes': self.nodes, 'connections': self.conn, 'active': False,
                'settings': dict({'executionOrder': 'v1', 'timezone': 'America/Sao_Paulo'}, **({'executionTimeout': TEMPO_MAXIMO} if self.wid != 'escCentral000001' else {})), 'pinData': {}, 'meta': {'templateCredsSetupCompleted': False}}
        with open(os.path.join(OUT, file), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')


def webhook(f, name, path, method, pos):
    return f.add(name, 'n8n-nodes-base.webhook', 2.1,
                 {'httpMethod': method, 'path': path, 'responseMode': 'responseNode', 'options': {'allowedOrigins': '*'}},
                 pos, webhookId=nid())


def respond(f, name, body, pos):
    return f.add(name, 'n8n-nodes-base.respondToWebhook', 1.4,
                 {'respondWith': 'json', 'responseBody': body, 'options': {'responseHeaders': CORS}}, pos)


def code(f, name, js, pos, **extra):
    return f.add(name, 'n8n-nodes-base.code', 2, {'jsCode': js.strip() + '\n'}, pos, **extra)


def http_json(f, name, method, url, body_expr, pos, headers=None, timeout=10000):
    p = {'method': method, 'url': url, 'options': {'timeout': timeout, 'response': {'response': {'fullResponse': True, 'neverError': True}}}}
    if body_expr is not None:
        p.update({'sendBody': True, 'specifyBody': 'json', 'jsonBody': body_expr})
    if headers:
        p.update({'sendHeaders': True, 'headerParameters': {'parameters': [{'name': k, 'value': v} for k, v in headers]}})
    # se o Central ou o WhatsApp estiverem fora, o agente continua o trabalho mesmo assim
    return f.add(name, 'n8n-nodes-base.httpRequest', 4.2, p, pos, onError='continueRegularOutput')


def evento(f, name, body_js, pos):
    return http_json(f, name, 'POST', "={{ $('Preparar').first().json.n8n }}/webhook/escritorio/evento",
                     '={{ JSON.stringify(' + body_js + ') }}', pos)


def agente_ia(f, name, model_name, system, prompt, pos, ferramentas):
    # Escolher cérebro -> AI Agent (pensa e usa as ferramentas) -> se der erro, marca o cérebro como fora e tenta o próximo
    code(f, 'Escolher cérebro', '''
// Cérebros do preferido para o reserva (o instalador ajusta). Quem falhou há pouco fica de fora por um tempo.
const CEREBROS = ''' + json.dumps(CEREBROS) + ''';
const s = $getWorkflowStaticData('global'); s.fora = s.fora || {};
const agora = Date.now();
const livres = CEREBROS.filter(m => !(s.fora[m] > agora));
const tentados = $input.first().json.tentados || [];
const modelo = livres.find(m => !tentados.includes(m)) || CEREBROS.find(m => !tentados.includes(m)) || CEREBROS[0];
return [{ json: Object.assign({}, $input.first().json, { modelo, tentados: tentados.concat(modelo) }) }];
''', [pos[0] - 220, pos[1]])
    f.add(name, '@n8n/n8n-nodes-langchain.agent', 2.2,
          {'promptType': 'define', 'text': prompt, 'options': {'systemMessage': system, 'maxIterations': 30, 'returnIntermediateSteps': True}},
          pos, onError='continueErrorOutput')
    f.add(model_name, '@n8n/n8n-nodes-langchain.lmChatOllama', 1,
          {'model': '={{ $json.modelo }}', 'options': dict(OLLAMA_OPCOES)}, [pos[0] - 120, pos[1] + 240])
    f.link(model_name, name, kind='ai_languageModel')
    f.link('Escolher cérebro', name)
    code(f, 'Trocar cérebro', '''
// o cérebro falhou: limite estourado ou fora do ar fica 30 min de fora; outro erro, 3 min. Tenta o próximo da lista.
const e = $json.error, msg = String(e && (e.message || e.description) || e || 'erro na IA');
const ctx = $('Escolher cérebro').last().json, s = $getWorkflowStaticData('global'); s.fora = s.fora || {};
const limite = /429|limit|quota|rate|unavailable|503|502|timeout|ECONNREFUSED|not found|unauthorized|401|403/i.test(msg);
s.fora[ctx.modelo] = Date.now() + (limite ? 30 : 3) * 60000;
const CEREBROS = ''' + json.dumps(CEREBROS) + ''';
const resta = CEREBROS.some(m => !ctx.tentados.includes(m));
const erros = (ctx.erros || []).concat(`${ctx.modelo}: ${msg.slice(0, 120)}`);
return [{ json: Object.assign({}, ctx, { tentarOutro: resta, erros, error: erros.join(' | ').slice(0, 600) }) }];
''', [pos[0] + 200, pos[1] + 260])
    f.link(name, 'Trocar cérebro', out=1)
    f.add('Tentar outro cérebro?', 'n8n-nodes-base.if', 2.2, {'conditions': {
        'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
        'conditions': [{'id': nid(), 'leftValue': '={{ $json.tentarOutro }}', 'rightValue': '', 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}],
        'combinator': 'and'}, 'options': {}}, [pos[0] + 420, pos[1] + 260])
    f.link('Trocar cérebro', 'Tentar outro cérebro?')
    f.link('Tentar outro cérebro?', 'Escolher cérebro', out=0)
    f.link('Tentar outro cérebro?', 'Avisar: erro', out=1)
    for i, ferramenta in enumerate(ferramentas):
        ferramenta(f, [pos[0] + 60 + i * 160, pos[1] + 240])
        f.link(f.nodes[-1]['name'], name, kind='ai_tool')


def ferramenta_http(f, nome, descricao, metodo, url, pos, corpo=None, json_body=None, placeholders=()):
    p = {'toolDescription': descricao, 'method': metodo, 'url': url}
    if corpo:
        p.update({'sendBody': True, 'specifyBody': 'keypair', 'parametersBody': {'values': corpo}})
    if json_body:
        p.update({'sendBody': True, 'specifyBody': 'json', 'jsonBody': json_body})
    if placeholders:
        p['placeholderDefinitions'] = {'values': [{'name': n, 'description': d, 'type': t} for n, d, t in placeholders]}
    return f.add(nome, '@n8n/n8n-nodes-langchain.toolHttpRequest', 1.1, p, pos)


def ver_telas(f, pos):
    return ferramenta_http(f, 'ver_telas', 'Mostra o que está aberto em cada tela do escritório (PCs, TV e Spotify): guias, sites e títulos.',
                           'GET', f'{N8N_INTERNO}/webhook/escritorio/telas', pos)


def usar_tela(agente):
    def criar(f, pos):
        return ferramenta_http(
            f, 'usar_tela', 'Usa uma tela do escritório: lê, clica, rola, abre um endereço, troca de guia, volta, digita, pergunta à IA aberta na tela (como o Claude) e espera a resposta. Devolve o que ficou na tela.',
            'POST', f'{N8N_INTERNO}/webhook/escritorio/tela', pos,
            corpo=[{'name': 'agente', 'valueProvider': 'fieldValue', 'value': agente},
                   {'name': 'tela', 'valueProvider': 'modelRequired'},
                   {'name': 'acao', 'valueProvider': 'modelRequired'},
                   {'name': 'alvo', 'valueProvider': 'modelOptional'}],
            placeholders=[('tela', 'qual tela: "meu pc", pc0 a pc5, tv, spotify, "PC 2" ou o nome do site aberto (ex.: whatsapp, claude)', 'string'),
                          ('acao', 'ler, clicar, rolar, abrir, guia, voltar, digitar, perguntar ou esperar', 'string'),
                          ('alvo', 'clicar: texto visível ou número do item da lista; rolar: baixo ou cima; abrir: endereço; guia: número; digitar: texto; perguntar: o pedido completo para a IA da tela; esperar: segundos', 'string')])
    return criar


def lembrar(agente):
    def criar(f, pos):
        return ferramenta_http(
            f, 'lembrar', 'Guarda uma instrução permanente que o Wes ensinou (como fazer, o que sempre ou nunca fazer). '
            'Ela passa a valer em todos os próximos pedidos. Use uma frase clara e completa.',
            'POST', f'{N8N_INTERNO}/webhook/escritorio/evento', pos,
            corpo=[{'name': 'agente', 'valueProvider': 'fieldValue', 'value': 'memoria'},
                   {'name': 'de', 'valueProvider': 'fieldValue', 'value': agente},
                   {'name': 'texto', 'valueProvider': 'modelRequired'}],
            placeholders=[('texto', 'a instrução, numa frase clara (ex.: "Sempre responder os clientes chamando pelo nome")', 'string')])
    return criar


def avisar_wes(agente):
    def criar(f, pos):
        return ferramenta_http(
            f, 'avisar_wes', 'Manda um recado curto para o Wes no meio da tarefa (o que você vai fazer agora ou o que já descobriu), sem terminar a tarefa.',
            'POST', f'{N8N_INTERNO}/webhook/escritorio/evento', pos,
            corpo=[{'name': 'agente', 'valueProvider': 'fieldValue', 'value': agente},
                   {'name': 'de', 'valueProvider': 'fieldValue', 'value': agente},
                   {'name': 'texto', 'valueProvider': 'modelRequired'}],
            placeholders=[('texto', 'o recado, em uma ou duas frases', 'string')])
    return criar


# ---------------------------------------------------------------- Central
TABELA = 'escritorio_registro'
COLUNAS = ['agente', 'status', 'tarefa', 'resultado', 'de', 'texto', 'evento', 'card', 'coluna']


TABELA_CMD = 'escritorio_comandos'  # pedidos dos agentes para as telas e as respostas do escritório
COLUNAS_CMD = ['agente', 'tela', 'acao', 'alvo', 'estado', 'resultado', 'ref']


def tabela(f, name, pos, nome=TABELA, **params):
    p = {'resource': 'row', 'dataTableId': {'__rl': True, 'mode': 'name', 'value': nome}}
    p.update(params)
    return f.add(name, 'n8n-nodes-base.dataTable', 1.1, p, pos)


def criar_tabela(f, name, pos, nome=TABELA, colunas=COLUNAS):
    # "reaproveitar se já existe": na primeira vez cria a tabela, depois só confirma que ela está lá
    return f.add(name, 'n8n-nodes-base.dataTable', 1.1,
                 {'resource': 'table', 'operation': 'create', 'tableName': nome,
                  'columns': {'column': [{'name': c, 'type': 'string'} for c in colunas]}, 'options': {'createIfNotExists': True}},
                 pos, executeOnce=True)


def respond_texto(f, name, body, pos):
    return f.add(name, 'n8n-nodes-base.respondToWebhook', 1.4,
                 {'respondWith': 'text', 'responseBody': body, 'options': {'responseHeaders': CORS}}, pos)


def central():
    # Cada aviso dos agentes (e cada mexida no kanban ou no mural) vira uma linha nova na tabela de dados "escritorio_registro" do n8n.
    # Só acrescentar linhas (sem reescrever um estado inteiro) evita que dois agentes falando ao mesmo tempo apaguem um ao outro.
    f = Flow('Escritório · Central dos agentes', 'escCentral000001')
    webhook(f, 'Escritório pergunta o estado', 'escritorio/estado', 'GET', [0, 0])
    criar_tabela(f, 'Garantir a tabela', [220, 0])
    tabela(f, 'Últimos avisos', [440, 0], operation='get', limit=400, orderBy=True, orderByColumn='createdAt', orderByDirection='DESC')
    f.nodes[-1]['alwaysOutputData'] = True  # tabela vazia: segue mesmo assim
    # as instruções permanentes vêm todas (não só as das últimas linhas), para nunca serem esquecidas
    tabela(f, 'Instruções guardadas', [550, 160], operation='get', returnAll=True, matchType='allConditions',
           filters={'conditions': [{'keyName': 'agente', 'condition': 'eq', 'keyValue': 'memoria'}]})
    f.nodes[-1].update(alwaysOutputData=True, executeOnce=True)
    criar_tabela(f, 'Garantir a tabela de comandos', [660, 0], nome=TABELA_CMD, colunas=COLUNAS_CMD)
    tabela(f, 'Comandos recentes', [880, 0], nome=TABELA_CMD, operation='get', limit=60, orderBy=True, orderByColumn='createdAt', orderByDirection='DESC')
    f.nodes[-1].update(alwaysOutputData=True, executeOnce=True)
    code(f, 'Montar estado', '''
// Quando um agente novo ganhar fluxo no n8n, coloque o id dele aqui.
const AGENTES_REAIS = ['fabio', 'ana', 'carla'];
// os avisos vêm do mais novo para o mais velho: aplica do mais velho para o mais novo
const recentes = $('Últimos avisos').all().map(i => i.json).filter(r => r && r.agente).reverse();
const vistos = new Set(recentes.map(r => r.id));
const guardadas = $('Instruções guardadas').all().map(i => i.json).filter(r => r && r.agente === 'memoria' && !vistos.has(r.id));
const linhas = guardadas.concat(recentes).sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt) || a.id - b.id);
const agentes = {}, conversas = {}, eventos = [], tarefas = [], abertas = {};
let mural = [], memorias = [];
const COLUNAS = ['afazer', 'fazendo', 'feito', 'erro'];
for (const r of linhas) {
  const t = new Date(r.createdAt).toISOString();
  // mural de avisos: agente "mural"; texto = aviso, status = cor; coluna "apagado" tira o aviso do card indicado
  // instruções permanentes: agente "memoria"; de = para quem (um agente ou "todos"); coluna "apagado" tira a do card indicado
  if (r.agente === 'memoria') {
    if (r.coluna === 'apagado') memorias = memorias.filter(n => n.id !== r.card);
    else if (r.texto) memorias.push({ id: String(r.id), agente: r.de || 'todos', texto: r.texto, t });
    continue;
  }
  if (r.agente === 'mural') {
    if (r.coluna === 'apagado') mural = mural.filter(n => n.id !== r.card);
    else if (r.texto) mural.push({ id: String(r.id), texto: r.texto, de: r.de || 'wes', cor: r.status || 'amarelo', t });
    continue;
  }
  // cartão movido à mão no kanban
  if (r.card && COLUNAS.includes(r.coluna)) {
    const c = tarefas.find(x => x.id === r.card);
    if (c) { c.coluna = r.coluna; c.atualizado = t; if (abertas[c.agente] === c && r.coluna !== 'fazendo' && r.coluna !== 'afazer') delete abertas[c.agente]; }
    continue;
  }
  // kanban: "trabalhando" ou "aguardando" abre (ou move) um cartão; "livre" ou "erro" fecha o cartão aberto do agente
  if ((r.status === 'trabalhando' || r.status === 'aguardando') && r.tarefa) {
    const coluna = r.status === 'trabalhando' ? 'fazendo' : 'afazer';
    let c = r.card ? tarefas.find(x => x.id === r.card) : null;
    if (!c && abertas[r.agente] && abertas[r.agente].tarefa === r.tarefa) c = abertas[r.agente];
    if (c) { c.coluna = coluna; c.atualizado = t; }
    else { c = { id: String(r.id), agente: r.agente, tarefa: r.tarefa, de: r.de || '', coluna, criado: t, atualizado: t }; tarefas.push(c); }
    abertas[r.agente] = c;
  } else if (r.status === 'livre' || r.status === 'erro') {
    // o agente diz qual cartão terminou; sem isso, fecha o último aberto dele
    const c = (r.card && tarefas.find(x => x.id === r.card)) || abertas[r.agente];
    if (c) { c.coluna = r.status === 'erro' ? 'erro' : 'feito'; c.resultado = r.resultado || ''; c.atualizado = t; }
    if (abertas[r.agente] === c) delete abertas[r.agente];
  }
  const a = agentes[r.agente] = agentes[r.agente] || {};
  // aviso só com mensagem (ex.: o Fábio avisando de um atraso) não muda o estado do agente
  if (r.status) { a.status = r.status; a.atualizado = t; a.rev = r.id; }
  if (r.tarefa != null) a.tarefa = r.tarefa;
  if (r.resultado != null) a.resultado = r.resultado;
  if (r.texto) (conversas[r.agente] = conversas[r.agente] || []).push({ de: r.de || 'wes', texto: r.texto, t });
  if (r.evento) eventos.unshift({ t, agente: r.agente, texto: r.evento });
}
for (const id in conversas) conversas[id] = conversas[id].slice(-40);
// no kanban vão todas as abertas e as 30 fechadas mais recentes
const fechadas = tarefas.filter(c => c.coluna === 'feito' || c.coluna === 'erro').sort((x, y) => y.atualizado.localeCompare(x.atualizado)).slice(0, 30);
const kanban = tarefas.filter(c => c.coluna === 'afazer' || c.coluna === 'fazendo').concat(fechadas);
// comandos dos agentes para as telas que o escritório ainda não respondeu (do último minuto e meio)
const cmds = $input.all().map(i => i.json).filter(r => r && r.estado);
const respondidos = new Set(cmds.filter(r => r.estado === 'resposta').map(r => String(r.ref)));
const comandos = cmds.filter(r => r.estado === 'pendente' && !respondidos.has(String(r.id)) && Date.now() - new Date(r.createdAt) < 90000)
  .map(r => ({ id: String(r.id), agente: r.agente, tela: r.tela, acao: r.acao, alvo: r.alvo || '', t: new Date(r.createdAt).toISOString() })).reverse();
const telas = ($getWorkflowStaticData('global').telas || {}).telas || [];
return [{ json: { versao: '__VERSAO__', ativos: AGENTES_REAIS, agentes, conversas, eventos: eventos.slice(0, 60), tarefas: kanban, mural: mural.slice(-24), memorias: memorias.slice(-60), telas, comandos, agora: new Date().toISOString() } }];
''', [1100, 0])
    respond(f, 'Responder estado', '={{ JSON.stringify($json) }}', [1320, 0])
    f.chain('Escritório pergunta o estado', 'Garantir a tabela', 'Últimos avisos', 'Instruções guardadas', 'Garantir a tabela de comandos', 'Comandos recentes', 'Montar estado', 'Responder estado')

    # ---- mapa das telas: só o escritório escreve (um escritor só, então pode ficar guardado no próprio fluxo)
    webhook(f, 'Escritório conta o que está nas telas', 'escritorio/mapa', 'POST', [0, 600])
    code(f, 'Guardar mapa', '''
const s = $getWorkflowStaticData('global');
let telas = [];
try { telas = JSON.parse($json.body.mapa || '[]'); } catch (e) {}
s.telas = { t: new Date().toISOString(), telas: Array.isArray(telas) ? telas.slice(0, 12).map(t => Object.assign(t, { conteudo: String(t.conteudo || '').slice(0, 2500) })) : [] };
return [{ json: { ok: true } }];
''', [220, 600])
    respond(f, 'Mapa guardado', '={{ JSON.stringify($json) }}', [440, 600])
    f.chain('Escritório conta o que está nas telas', 'Guardar mapa', 'Mapa guardado')

    webhook(f, 'Agente olha as telas', 'escritorio/telas', 'GET', [0, 800])
    code(f, 'Descrever telas', '''
const m = $getWorkflowStaticData('global').telas || {};
const telas = m.telas || [];
if (!telas.length) return [{ json: { texto: 'O escritório não contou o que está nas telas (ele está fechado?).' } }];
const linhas = telas.map(t => `${t.tela} · ${t.nome}${t.mesa ? ' (mesa de ' + t.mesa + ')' : ''}\\n` + (t.guias || []).map(g =>
  `   guia ${g.n}${g.ativa ? ' (na frente)' : ''}: ${g.titulo || '(sem título)'} — ${g.url}${g.tocando ? ' · tocando som' : ''}`).join('\\n')
  + (t.conteudo ? `\\n   conteúdo da guia da frente:\\n   ${t.conteudo.replace(/\\n/g, '\\n   ')}` : ''));
return [{ json: { texto: `Telas do escritório (atualizado ${m.t}):\\n` + linhas.join('\\n') } }];
''', [220, 800])
    respond_texto(f, 'Mostrar telas', '={{ $json.texto }}', [440, 800])
    f.chain('Agente olha as telas', 'Descrever telas', 'Mostrar telas')

    # ---- agente usa uma tela: o pedido entra na fila, o escritório faz e responde, e este fluxo espera a resposta
    webhook(f, 'Agente usa uma tela', 'escritorio/tela', 'POST', [0, 1000])
    criar_tabela(f, 'Garantir a tabela de comandos (tela)', [220, 1000], nome=TABELA_CMD, colunas=COLUNAS_CMD)
    code(f, 'Montar comando', '''
const b = $('Agente usa uma tela').first().json.body || {};
const t = (v, max) => String(v == null ? '' : v).trim().slice(0, max);
return [{ json: { agente: t(b.agente, 20), tela: t(b.tela, 60), acao: t(b.acao, 20).toLowerCase(), alvo: t(b.alvo, 500), estado: 'pendente' } }];
''', [440, 1000])
    tabela(f, 'Guardar comando', [660, 1000], nome=TABELA_CMD, operation='insert',
           columns={'mappingMode': 'autoMapInputData', 'value': {}, 'matchingColumns': [], 'schema': []}, options={})
    f.add('Esperar o escritório', 'n8n-nodes-base.wait', 1.1, {'resume': 'timeInterval', 'amount': 1, 'unit': 'seconds'}, [880, 1000], webhookId=nid())
    tabela(f, 'Respostas recentes', [1100, 1000], nome=TABELA_CMD, operation='get', limit=60, orderBy=True, orderByColumn='createdAt', orderByDirection='DESC')
    f.nodes[-1].update(alwaysOutputData=True, executeOnce=True)
    code(f, 'Chegou a resposta?', '''
// espera o escritório responder: ~45 s numa ação comum; até ~3 min quando a IA da tela (Claude) está respondendo
const id = String($('Guardar comando').first().json.id), acao = $('Montar comando').first().json.acao;
const r = $input.all().map(i => i.json).find(x => x && x.estado === 'resposta' && String(x.ref) === id);
if (r) return [{ json: { pronto: true, resultado: r.resultado || '(sem resposta)' } }];
const limite = acao === 'perguntar' ? 170 : acao === 'esperar' ? 110 : 44;
if ($runIndex >= limite) return [{ json: { pronto: true, resultado: 'O escritório não respondeu: ele precisa estar aberto no Chrome, com a extensão, para usar as telas.' } }];
return [{ json: { pronto: false } }];
''', [1320, 1000])
    f.add('Pronto?', 'n8n-nodes-base.if', 2.2, {'conditions': {
        'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
        'conditions': [{'id': nid(), 'leftValue': '={{ $json.pronto }}', 'rightValue': '', 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}],
        'combinator': 'and'}, 'options': {}}, [1540, 1000])
    respond_texto(f, 'Devolver o resultado', '={{ $json.resultado }}', [1760, 940])
    f.chain('Agente usa uma tela', 'Garantir a tabela de comandos (tela)', 'Montar comando', 'Guardar comando', 'Esperar o escritório', 'Respostas recentes', 'Chegou a resposta?', 'Pronto?')
    f.link('Pronto?', 'Devolver o resultado', out=0)
    f.link('Pronto?', 'Esperar o escritório', out=1)

    # ---- o escritório devolve o resultado de um comando
    webhook(f, 'Escritório devolve o resultado', 'escritorio/resposta', 'POST', [0, 1300])
    criar_tabela(f, 'Garantir a tabela de comandos (resposta)', [220, 1300], nome=TABELA_CMD, colunas=COLUNAS_CMD)
    code(f, 'Montar resposta', '''
const b = $('Escritório devolve o resultado').first().json.body || {};
return [{ json: { ref: String(b.ref || ''), estado: 'resposta', resultado: String(b.resultado || '').slice(0, 12000) } }];
''', [440, 1300])
    tabela(f, 'Guardar resposta', [660, 1300], nome=TABELA_CMD, operation='insert',
           columns={'mappingMode': 'autoMapInputData', 'value': {}, 'matchingColumns': [], 'schema': []}, options={})
    respond(f, 'Resposta guardada', '={{ JSON.stringify({ ok: true }) }}', [880, 1300])
    f.chain('Escritório devolve o resultado', 'Garantir a tabela de comandos (resposta)', 'Montar resposta', 'Guardar resposta', 'Resposta guardada')

    webhook(f, 'Agente avisa o que está fazendo', 'escritorio/evento', 'POST', [0, 300])
    criar_tabela(f, 'Garantir a tabela (aviso)', [220, 300])
    code(f, 'Montar linha', '''
// Cada agente manda (JSON): { agente, status, tarefa, resultado, mensagem: { de, texto }, evento, card }
// status: trabalhando | livre | erro | aguardando. Campo que não veio fica vazio e não muda nada.
// O escritório manda como formulário, com de e texto soltos, e card + coluna para mexer no kanban e no mural.
const b = $('Agente avisa o que está fazendo').first().json.body || {};
const txt = (v, max) => v === undefined || v === null || v === '' ? null : String(v).slice(0, max);
const m = b.mensagem && b.mensagem.texto ? b.mensagem : b.texto ? { de: b.de, texto: b.texto } : null;
return [{ json: {
  card: txt(b.card, 40), coluna: txt(b.coluna, 20),
  agente: String(b.agente || 'desconhecido').toLowerCase().replace(/[^a-z]/g, '') || 'desconhecido',
  status: txt(b.status, 20), tarefa: txt(b.tarefa, 500), resultado: txt(b.resultado, 6000),
  de: m ? String(m.de || 'wes').slice(0, 20) : null, texto: m ? String(m.texto).slice(0, 6000) : null, evento: txt(b.evento, 300),
} }];
''', [440, 300])
    tabela(f, 'Guardar aviso', [660, 300], operation='insert',
           columns={'mappingMode': 'autoMapInputData', 'value': {}, 'matchingColumns': [], 'schema': []}, options={})
    respond(f, 'Confirmar', '={{ JSON.stringify({ ok: true, id: String($json.id) }) }}', [880, 300])
    f.chain('Agente avisa o que está fazendo', 'Garantir a tabela (aviso)', 'Montar linha', 'Guardar aviso', 'Confirmar')
    # ---- o Wes aperta "Enviar" no cartão da mensagem que a Ana preparou: o envio sai pela Evolution (sem usar as telas).
    # Só o escritório (com o código desta instalação) pode pedir; a IA não chama este caminho.
    webhook(f, 'Wes manda enviar no WhatsApp', 'escritorio/whatsapp-enviar', 'POST', [0, 1600])
    code(f, 'Conferir envio', '''
// ===== configuração (o instalador preenche) =====
const EVOLUTION_URL = '';   // ex.: http://localhost:8080
const EVOLUTION_KEY = '';
const INSTANCIA = 'cantinho-comercial';
const CODIGO_ENVIO = '';    // código desta instalação: só o escritório conhece
// =================================================
const b = $json.body || {};
const numero = String(b.numero || '').trim().replace(/[^0-9@a-z.]/gi, '');
const texto = String(b.texto || '').trim().slice(0, 3000);
let erro = '';
if (!EVOLUTION_URL || !EVOLUTION_KEY) erro = 'a Evolution não está configurada (rode o instalar.bat)';
else if (!CODIGO_ENVIO || b.codigo !== CODIGO_ENVIO) erro = 'pedido de envio sem o código do escritório';
else if (!/^\\d{10,15}$|@/.test(numero)) erro = 'número inválido: ' + numero;
else if (!texto) erro = 'mensagem vazia';
return [{ json: { ok: !erro, erro, numero, texto, nome: String(b.nome || '').slice(0, 80), url: `${EVOLUTION_URL}/message/sendText/${INSTANCIA}`, key: EVOLUTION_KEY } }];
''', [220, 1600])
    f.add('Pode enviar?', 'n8n-nodes-base.if', 2.2, {'conditions': {
        'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
        'conditions': [{'id': nid(), 'leftValue': '={{ $json.ok }}', 'rightValue': '', 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}],
        'combinator': 'and'}, 'options': {}}, [440, 1600])
    http_json(f, 'Enviar pela Evolution', 'POST', '={{ $json.url }}', '={{ JSON.stringify({ number: $json.numero, text: $json.texto }) }}', [660, 1540],
              headers=[('apikey', '={{ $json.key }}')], timeout=30000)
    code(f, 'Resultado do envio', '''
const c = $('Conferir envio').first().json, r = $json;
const ok = (r.statusCode || 0) >= 200 && (r.statusCode || 0) < 300;
const erro = ok ? '' : 'a Evolution recusou (' + (r.statusCode || 'sem resposta') + '): ' + JSON.stringify(r.body || r.error || '').slice(0, 200);
return [{ json: { ok, erro, numero: c.numero, nome: c.nome } }];
''', [880, 1540])
    respond(f, 'Envio: resposta', '={{ JSON.stringify($json) }}', [1100, 1540])
    respond(f, 'Envio recusado', '={{ JSON.stringify({ ok: false, erro: $json.erro }) }}', [660, 1700])
    f.chain('Wes manda enviar no WhatsApp', 'Conferir envio', 'Pode enviar?')
    f.link('Pode enviar?', 'Enviar pela Evolution', out=0)
    f.link('Pode enviar?', 'Envio recusado', out=1)
    f.chain('Enviar pela Evolution', 'Resultado do envio', 'Envio: resposta')
    f.save('escritorio-central.json')


# ---------------------------------------------------------------- partes comuns dos agentes
def preparar_js(agente, extra_cfg=''):
    extra_campos = ''.join(', ' + k for k in ['evolutionUrl', 'evolutionKey', 'instancia', 'abekyo'] if k + ' =' in extra_cfg)
    return f'''
// ===== configuração =====
const N8N = '{N8N_INTERNO}';   // endereço do n8n visto de dentro dele mesmo
{extra_cfg}
// ========================
const b = $json.body || {{}};
const card = String(b.card || '').slice(0, 40);   // cartão do kanban, quando o pedido veio de lá
const texto = String(b.texto || '').trim().slice(0, 4000);
if (!texto) return [];
const de = String(b.de || 'wes').toLowerCase();
const quem = {{ wes: 'Wes (o dono)', fabio: 'Fábio (gestor)' }}[de] || de;
return [{{ json: {{ n8n: N8N, agente: '{agente}', texto, de, quem, card{extra_campos} }} }}];
'''


CONTEXTO_COMUM = '''
const p = $('Preparar').first().json;
const est = ($('Ler estado do escritório').first().json || {}).body || {};
// conversa recente com este agente (a última mensagem é o próprio pedido, que já foi registrado)
const conv = ((est.conversas || {})[p.agente] || []).slice(-11, -1);
const nomes = { wes: 'Wes', fabio: 'Fábio', ana: 'Ana', bruno: 'Bruno', carla: 'Carla', davi: 'Davi', eva: 'Eva' };
const historico = conv.map(m => `${nomes[m.de] || m.de}: ${m.texto}`).join('\\n') || '(sem conversa anterior)';
const equipe = Object.entries(est.agentes || {}).map(([id, a]) => `${nomes[id] || id}: ${a.status || '?'}${a.tarefa ? ' · ' + a.tarefa : ''}`).join('\\n') || '(sem dados)';
const agora = new Date().toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo', dateStyle: 'full', timeStyle: 'short' });
const mural = (est.mural || []).map(n => `- ${n.texto} (${nomes[n.de] || n.de})`).join('\\n') || '(vazio)';
const abertas = (est.tarefas || []).filter(c => c.coluna === 'afazer' || c.coluna === 'fazendo').map(c => `- ${nomes[c.agente] || c.agente} · ${c.coluna === 'fazendo' ? 'fazendo' : 'a fazer'}: ${c.tarefa}`).join('\\n') || '(nenhuma)';
// o que está aberto em cada tela do escritório agora
const telas = (est.telas || []).map(t => `- ${t.tela} · ${t.nome}: ` + ((t.guias || []).map(g => `${g.ativa ? '[na frente] ' : ''}${g.titulo || '(sem título)'} (${String(g.url || '').replace(/^https?:\\/\\//, '').slice(0, 60)})`).join(' | ') || 'vazia')
    + (t.conteudo ? `\\n  conteúdo da guia da frente: ${t.conteudo.slice(0, 1500).replace(/\\n/g, ' ¶ ')}` : '')).join('\\n')
  || '(o escritório está fechado agora, ou sem a extensão: sem telas)';
// diagnóstico da equipe: o que está parado, há quanto tempo e por quê (o Fábio usa para explicar atrasos)
const agoraMs = Date.now(), minDe = t => Math.max(0, Math.round((agoraMs - new Date(t)) / 60000));
const reais = new Set(est.ativos || []), pend = est.comandos || [], diag = [];
for (const c of (est.tarefas || [])) {
  const quem = nomes[c.agente] || c.agente, m = minDe(c.atualizado || c.criado);
  if (c.coluna === 'fazendo') diag.push(`- ${quem} está fazendo “${c.tarefa}” há ${m} min` + (m < 5 ? '' : pend.some(x => x.agente === c.agente)
    ? ' (demorando: esperando uma tela responder; o escritório precisa estar aberto no Chrome com a extensão)'
    : ' (demorando: pode estar esperando a IA (Ollama) ou o editor de vídeo, ou travou; se passar de 10 min, mova o cartão para A fazer e peça de novo)'));
  else if (c.coluna === 'afazer') diag.push(`- “${c.tarefa}” (${quem}) está parada em A fazer há ${m} min: ` + (reais.has(c.agente)
    ? `ninguém pediu para ${quem} fazer agora (no kanban: “Pedir para ${quem} fazer agora”)` : `${quem} ainda não tem função no n8n`));
  else if (c.coluna === 'erro' && m < 240) diag.push(`- “${c.tarefa}” (${quem}) não foi feita, deu erro há ${m} min: ${String(c.resultado || '').slice(0, 200)}`);
}
for (const x of pend) if (minDe(x.t) >= 1) diag.push(`- ${nomes[x.agente] || x.agente} pediu para ${x.acao} na tela ${x.tela} e o escritório ainda não respondeu (está aberto no Chrome com a extensão?)`);
if (!(est.telas || []).length) diag.push('- O escritório está fechado ou sem a extensão: ninguém consegue usar as telas agora.');
const diagnostico = diag.join('\\n') || '(tudo em dia: nenhuma tarefa parada, demorando ou com erro)';
// instruções permanentes que o Wes ensinou (a este agente ou a todos)
const memorias = (est.memorias || []).filter(m => m.agente === p.agente || m.agente === 'todos').map(m => `- ${m.texto}`).join('\\n') || '(nenhuma ainda)';
'''


PARADA_JS = '\n// o agente parou por tentar demais: explica o que tentou, em vez de "Agent stopped due to max iterations"\nconst passos = ($json.intermediateSteps || []).slice(-4).map(x => `- ${x.action && x.action.tool}: ${String(JSON.stringify((x.action && x.action.toolInput) || \'\')).slice(0, 120)} → ${String(x.observation || \'\').replace(/\\s+/g, \' \').slice(0, 160)}`).join(\'\\n\');\nconst parou = /max iterations|stopped due to/i.test(String($json.output || \'\'));\nconst textoParou = \'Parei porque tentei muitas vezes e não consegui terminar.\' + (passos ? \'\\n\\nMeus últimos passos:\\n\' + passos : \'\') + \'\\n\\nMe diga se quer que eu tente de outro jeito.\';\n'


def inicio_agente(f, agente, extra_cfg=''):
    webhook(f, 'Pedido chega', f'escritorio/{agente}', 'POST', [0, 0])
    respond(f, 'Recebido', '={{ JSON.stringify({ ok: true }) }}', [220, 0])
    code(f, 'Preparar', preparar_js(agente, extra_cfg), [440, 0])
    evento(f, 'Avisar: trabalhando', "{ agente: $json.agente, status: 'trabalhando', tarefa: $json.texto, card: $json.card || undefined, mensagem: { de: $json.de, texto: $json.texto }, evento: 'recebeu de ' + $json.quem + ': ' + $json.texto }", [660, 0])
    http_json(f, 'Ler estado do escritório', 'GET', "={{ $('Preparar').first().json.n8n }}/webhook/escritorio/estado", None, [880, 0])
    f.chain('Pedido chega', 'Recebido', 'Preparar', 'Avisar: trabalhando')


def fim_agente(f, depois_de, x):
    evento(f, 'Avisar: pronto', "{ card: $('Preparar').first().json.card || ($('Avisar: trabalhando').first().json.body || {}).id, agente: $('Preparar').first().json.agente, status: 'livre', tarefa: '', resultado: $json.resposta, mensagem: { de: $('Preparar').first().json.agente, texto: $json.resposta }, evento: 'terminou (cérebro: ' + ($('Escolher cérebro').isExecuted ? $('Escolher cérebro').last().json.modelo : '-') + '): ' + $('Preparar').first().json.texto }", [x, 0])
    f.link(depois_de, 'Avisar: pronto')
    evento(f, 'Avisar: erro', "{ card: $('Preparar').first().json.card || ($('Avisar: trabalhando').first().json.body || {}).id, agente: $('Preparar').first().json.agente, status: 'erro', tarefa: '', resultado: 'Não consegui terminar: ' + ($json.error && $json.error.message || $json.error || 'erro na IA'), mensagem: { de: $('Preparar').first().json.agente, texto: 'Não consegui terminar agora: nenhum cérebro (IA) respondeu. ' + (/401|unauthori|sign ?in/i.test(String($json.error || '')) ? 'Os modelos da nuvem do Ollama pedem login: rode o instalar.bat (ele abre o login do Ollama).' : /ECONNREFUSED|fetch failed|connect/i.test(String($json.error || '')) ? 'O Ollama está desligado: abra o Ollama ou o abrir-escritorio.bat.' : 'Tente de novo daqui a pouco.') + ' (' + String($json.error || '').slice(0, 160) + ')' }, evento: 'deu erro em: ' + $('Preparar').first().json.texto }", [x - 220, 260])


# ---------------------------------------------------------------- Fábio
def fabio():
    f = Flow('Escritório · Fábio (Gestor)', 'escFabio00000001')
    inicio_agente(f, 'fabio')
    code(f, 'Montar contexto', CONTEXTO_COMUM + '''
return [{ json: { memorias, historico, equipe, agora, mural, abertas, telas, diagnostico } }];
''', [1100, 0])
    f.chain('Avisar: trabalhando', 'Ler estado do escritório', 'Montar contexto')
    sistema = f'''Você é o Fábio, gestor da equipe de agentes de IA do Wes. Seu computador é o PC 6 (pc5). O Wes é dono do Cantinho do Au Au (creche, hotel e banho e tosa de cães, em São Paulo) e da Mentoria Creche Milionária.
Seu trabalho: entender o pedido, responder o Wes de forma curta e direta, e passar tarefas para quem da equipe pode fazer.
Você é o encarregado: responde pela equipe. Quando o Wes perguntar por que uma tarefa demorou, não foi feita ou deu errado (ou quando você perceber isso), explique o motivo com o "Diagnóstico da equipe" e diga o que fazer para destravar. Nunca responda só "não sei": diga o que você conferiu.

Equipe:
{EQUIPE}

Regras:
- Responda em português do Brasil, em poucas linhas.
- Só passe tarefa para quem faz sentido. Pode passar para quem ainda não tem função: a tarefa fica guardada esperando, e você avisa o Wes disso.
- Se você mesmo consegue responder (organizar, priorizar, planejar, escrever um texto curto), responda sem passar para ninguém.
- Nunca diga que mandou mensagem para cliente: a Ana prepara e o Wes aprova o envio no chat dela. Pedido para mandar mensagem a alguém: passe para a ana.
- Carrossel, roteiro, legenda ou vídeo: passe para a carla.
- Leve em conta os avisos do mural e as tarefas que já estão abertas no kanban (não passe de novo o que já está lá).
- Quando pedirem para avisar a equipe ou colar algo no mural, escreva o aviso em "aviso" (curto, como um post-it).
- Ao passar uma tarefa que envolve uma tela, diga ao agente qual tela é (veja "Telas agora"), por exemplo: "o WhatsApp está aberto no pc1".

{TELAS_REGRAS}

Responda SOMENTE com um JSON neste formato, sem texto fora dele:
{{"resposta": "o que você diz para quem pediu", "delegar": [{{"agente": "ana", "tarefa": "pedido claro e completo para ela"}}], "aviso": ""}}
Use "delegar": [] quando não passar nada para ninguém, e "aviso": "" quando não for colar nada no mural.'''
    prompt = '''=Agora: {{ $json.agora }}

Como está a equipe agora:
{{ $json.equipe }}

Tarefas abertas no kanban:
{{ $json.abertas }}

Mural de avisos:
{{ $json.mural }}

Diagnóstico da equipe (o que está parado e por quê):
{{ $json.diagnostico }}

Telas agora:
{{ $json.telas }}

Instruções permanentes do Wes (siga sempre):
{{ $json.memorias }}

Conversa recente com você:
{{ $json.historico }}

Novo pedido de {{ $('Preparar').first().json.quem }}:
{{ $('Preparar').first().json.texto }}'''
    agente_ia(f, 'Fábio pensa', 'Cérebro do Fábio', sistema, prompt, [1320, 0], [ver_telas, usar_tela('fabio'), lembrar('fabio'), avisar_wes('fabio')])
    f.link('Montar contexto', 'Escolher cérebro')
    code(f, 'Ler resposta', PARADA_JS + '''
const raw = parou ? JSON.stringify({ resposta: textoParou }) : String($json.output || $json.text || '').trim();
let out = null;
try { const m = raw.match(/\\{[\\s\\S]*\\}/); out = JSON.parse(m ? m[0] : raw); } catch (e) {}
const validos = { ana: 'Ana', bruno: 'Bruno', carla: 'Carla', davi: 'Davi', eva: 'Eva' };
const delegar = (out && Array.isArray(out.delegar) ? out.delegar : [])
  .map(d => ({ agente: String(d && d.agente || '').toLowerCase().trim(), tarefa: String(d && d.tarefa || '').trim() }))
  .filter(d => validos[d.agente] && d.tarefa).slice(0, 5);
let resposta = out && out.resposta ? String(out.resposta).trim() : raw;
if (delegar.length) resposta += '\\n\\nPassei para: ' + delegar.map(d => `${validos[d.agente]} (${d.tarefa})`).join('; ');
const aviso = out && out.aviso ? String(out.aviso).trim().slice(0, 400) : '';
if (aviso) resposta += '\\n\\nColei no mural: ' + aviso;
return [{ json: { resposta, delegar, aviso } }];
''', [1600, 0])
    f.link('Fábio pensa', 'Ler resposta')
    fim_agente(f, 'Ler resposta', 1820)
    code(f, 'Separar tarefas', '''
return $('Ler resposta').first().json.delegar.map(d => ({ json: d }));
''', [2040, 0])
    f.link('Avisar: pronto', 'Separar tarefas')
    http_json(f, 'Passar tarefa', 'POST', "={{ $('Preparar').first().json.n8n }}/webhook/escritorio/{{ $json.agente }}",
              "={{ JSON.stringify({ texto: $json.tarefa, de: 'fabio' }) }}", [2260, 0])
    f.link('Separar tarefas', 'Passar tarefa')
    code(f, 'Quem ainda não tem fluxo', '''
// o webhook do agente não existe (404): a tarefa fica guardada para ele, esperando
const tarefas = $('Separar tarefas').all();
return $input.all().map((it, i) => ({ ok: (it.json.statusCode || 0) >= 200 && (it.json.statusCode || 0) < 300, d: tarefas[i] && tarefas[i].json }))
  .filter(x => !x.ok && x.d)
  .map(x => ({ json: { agente: x.d.agente, status: 'aguardando', tarefa: x.d.tarefa, mensagem: { de: 'fabio', texto: x.d.tarefa }, evento: 'recebeu do Fábio (ainda sem função): ' + x.d.tarefa } }));
''', [2480, 0])
    f.link('Passar tarefa', 'Quem ainda não tem fluxo')
    code(f, 'Tem aviso para o mural?', '''
const aviso = $('Ler resposta').first().json.aviso;
return aviso ? [{ json: { agente: 'mural', texto: aviso, de: 'fabio', status: 'azul' } }] : [];
''', [2040, 260])
    f.link('Ler resposta', 'Tem aviso para o mural?')
    evento(f, 'Colar no mural', '$json', [2260, 260])
    f.link('Tem aviso para o mural?', 'Colar no mural')
    evento(f, 'Guardar tarefa esperando', '$json', [2700, 0])
    f.link('Quem ainda não tem fluxo', 'Guardar tarefa esperando')
    f.add('A cada 2 minutos', 'n8n-nodes-base.scheduleTrigger', 1.2, {'rule': {'interval': [{'field': 'minutes', 'minutesInterval': 2}]}}, [0, 600])
    http_json(f, 'Ler estado (vigia)', 'GET', f'{N8N_INTERNO}/webhook/escritorio/estado', None, [220, 600])
    code(f, 'Achar atrasos e erros', '''
// O Fábio vigia a equipe: tarefa demorando, com erro ou parada sem dono vira um aviso para o Wes (uma vez por problema).
const est = $json.body || {};
if (!est.tarefas) return [];
const s = $getWorkflowStaticData('global'); s.avisados = s.avisados || {};
const nomes = { fabio: 'Fábio', ana: 'Ana', bruno: 'Bruno', carla: 'Carla', davi: 'Davi', eva: 'Eva' };
const agora = Date.now(), minDe = t => Math.round((agora - new Date(t)) / 60000), reais = new Set(est.ativos || []);
const novos = [];
for (const c of est.tarefas) {
  const quem = nomes[c.agente] || c.agente, m = minDe(c.atualizado || c.criado);
  if (c.coluna === 'fazendo' && m >= 5 && !s.avisados['lento:' + c.id]) {
    s.avisados['lento:' + c.id] = agora;
    const tela = (est.comandos || []).some(x => x.agente === c.agente);
    novos.push(`⏳ ${quem} está há ${m} min em “${c.tarefa}”. ` + (tela ? 'Está esperando uma tela responder: confira se o escritório está aberto no Chrome com a extensão.'
      : 'Pode estar esperando a IA (Ollama) ou o editor de vídeo, ou travou. Se passar de 10 min, mova o cartão para A fazer no kanban e peça de novo.'));
  } else if (c.coluna === 'erro' && m <= 30 && !s.avisados['erro:' + c.id]) {
    s.avisados['erro:' + c.id] = agora;
    novos.push(`⚠️ ${quem} não conseguiu fazer “${c.tarefa}”: ${String(c.resultado || 'sem detalhe').slice(0, 220)}. Quer que eu peça de novo?`);
  } else if (c.coluna === 'afazer' && !reais.has(c.agente) && m >= 10 && !s.avisados['semfuncao:' + c.id]) {
    s.avisados['semfuncao:' + c.id] = agora;
    novos.push(`📌 “${c.tarefa}” está parada porque ${quem} ainda não tem função no n8n.`);
  }
}
for (const x of (est.comandos || [])) if (minDe(x.t) >= 1 && !s.avisados['tela:' + x.id]) {
  s.avisados['tela:' + x.id] = agora;
  novos.push(`🖥️ ${nomes[x.agente] || x.agente} tentou usar a tela ${x.tela} e o escritório não respondeu: ele precisa estar aberto no Chrome com a extensão.`);
}
// esquece avisos com mais de 2 dias
for (const k in s.avisados) if (agora - s.avisados[k] > 2 * 86400000) delete s.avisados[k];
if (!novos.length) return [];
return [{ json: { agente: 'fabio', mensagem: { de: 'fabio', texto: 'Wes, ' + (novos.length > 1 ? 'olha o que está pegando na equipe:\\n' + novos.join('\\n') : novos[0].replace(/^\\S+ /, '')) }, evento: 'avisou o Wes: ' + novos.length + ' problema(s)' } }];
''', [440, 600])
    http_json(f, 'Avisar o Wes', 'POST', f'{N8N_INTERNO}/webhook/escritorio/evento', '={{ JSON.stringify($json) }}', [660, 600])
    f.chain('A cada 2 minutos', 'Ler estado (vigia)', 'Achar atrasos e erros', 'Avisar o Wes')
    f.save('agente-fabio.json')


# ---------------------------------------------------------------- Ana
def ana():
    f = Flow('Escritório · Ana (Comercial)', 'escAna0000000001')
    inicio_agente(f, 'ana', '''const EVOLUTION_URL = 'http://evolution-api:8080';   // Evolution API vista de dentro do n8n (mesmo endereço que os fluxos do agente comercial usam)
const EVOLUTION_KEY = '';                              // apikey da Evolution (a mesma dos fluxos do agente comercial)
const INSTANCIA = 'cantinho-comercial';
const evolutionUrl = EVOLUTION_URL.replace(/\\/+$/, ''), evolutionKey = EVOLUTION_KEY, instancia = INSTANCIA;''')
    http_json(f, 'WhatsApp: conversas', 'POST', "={{ $('Preparar').first().json.evolutionUrl }}/chat/findChats/{{ $('Preparar').first().json.instancia }}",
              '={{ JSON.stringify({}) }}', [1100, 0], headers=[('apikey', "={{ $('Preparar').first().json.evolutionKey }}")], timeout=20000)
    f.chain('Avisar: trabalhando', 'Ler estado do escritório', 'WhatsApp: conversas')
    code(f, 'Montar contexto', CONTEXTO_COMUM + '''
// ---- conversas do WhatsApp comercial: quem está esperando resposta e quem está no ponto de follow-up
const r = $('WhatsApp: conversas').first().json || {};
const lista = !p.evolutionUrl ? null : Array.isArray(r.body) ? r.body : Array.isArray(r.body && r.body.chats) ? r.body.chats : null;
const textoDe = m => { m = m || {}; return m.conversation || (m.extendedTextMessage || {}).text || (m.imageMessage || {}).caption || (m.videoMessage || {}).caption
  || (m.audioMessage ? '[áudio]' : m.imageMessage ? '[imagem]' : m.documentMessage ? '[documento]' : m.stickerMessage ? '[figurinha]' : ''); };
const REGUA = [[14, 'R5'], [7, 'R4'], [4, 'R3'], [2, 'R2'], [1, 'R1']];
const agoraS = Date.now() / 1000;
let whatsapp;
if (!lista) {
  // sem a leitura direta (Evolution não configurada ou fora do ar): a Ana trabalha pelo WhatsApp Web aberto numa tela
  whatsapp = '';
} else {
  const linhas = [], cont = { responder: 0, followup: 0 };
  for (const c of lista) {
    const jid = String(c.remoteJid || c.id || '');
    if (!jid || /@g\\.us|@broadcast|@newsletter/.test(jid)) continue;
    const lm = c.lastMessage || null;
    const ts = Number(lm && lm.messageTimestamp) || (Date.parse(c.updatedAt) / 1000) || 0;
    if (!ts) continue;
    const dias = (agoraS - ts) / 86400;
    if (dias > 30) continue;
    const nome = c.pushName || (lm && lm.pushName) || jid.split('@')[0];
    const fone = jid.endsWith('@s.whatsapp.net') ? jid.split('@')[0] : jid;
    const ultimo = textoDe(lm && lm.message).replace(/\\s+/g, ' ').slice(0, 160);
    const quando = dias < 1 ? `há ${Math.max(1, Math.round(dias * 24))}h` : `há ${Math.round(dias)} dia(s)`;
    const doCliente = lm && lm.key && lm.key.fromMe === false;
    if (doCliente) { cont.responder++; linhas.push({ p: 0, o: -dias, t: `- ESPERANDO RESPOSTA · ${nome}${fone ? ' (' + fone + ')' : ''} · cliente escreveu ${quando}: "${ultimo}"` }); }
    else if (lm && lm.key && lm.key.fromMe) {
      const r5 = REGUA.find(([d]) => dias >= d);
      if (r5) { cont.followup++; linhas.push({ p: 1, o: -dias, t: `- FOLLOW-UP ${r5[1]} · ${nome}${fone ? ' (' + fone + ')' : ''} · nossa última mensagem ${quando}: "${ultimo}"` }); }
    }
  }
  linhas.sort((a, b) => a.p - b.p || a.o - b.o);
  whatsapp = `${lista.length} conversas lidas. ${cont.responder} esperando resposta, ${cont.followup} no ponto de follow-up (régua pelo tempo desde a nossa última mensagem).\\n`
    + (linhas.slice(0, 30).map(l => l.t).join('\\n') || '(nenhuma conversa pendente)');
}
const whatsappSecao = whatsapp ? `Conversas do WhatsApp comercial (leitura direta pela Evolution):\\n${whatsapp}\\n\\n` : '';
return [{ json: { memorias, historico, equipe, agora, whatsappSecao, telas } }];
''', [1320, 0])
    f.link('WhatsApp: conversas', 'Montar contexto')
    sistema = '''Você é a Ana, agente comercial do Cantinho do Au Au (creche, hotel e banho e tosa de cães, em São Paulo). Você trabalha com a Mari, que é quem conversa com os clientes no WhatsApp comercial. Seu computador é o PC 1 (pc0).

O que você faz:
- Trabalha pelo WhatsApp Web aberto nos computadores do escritório (veja "Telas agora"): lê a lista de conversas e as mensagens, aponta quem está esperando resposta e quem está no ponto de follow-up. Quando houver leitura direta pela Evolution, ela também aparece no pedido (é a fonte mais confiável).
- É proativa: ao receber um pedido sobre clientes, já lê as conversas, abre as que importam e entrega a lista com as mensagens prontas, sem perguntar antes. Quando o Wes pedir para "responder" alguém, entregue a resposta pronta para copiar e diga para quem é (nome e número).
- Responde qualquer pergunta sobre o que está nas telas (por exemplo, quem mandou a última mensagem: é a primeira conversa da lista do WhatsApp).
- Escreve as mensagens, prontas para o Wes aprovar e enviar com um clique (ou para a Mari copiar).
- Régua de follow-up depois da nossa última mensagem sem resposta: R1 em D+1, R2 em D+2, R3 em D+4, R4 em D+7, R5 em D+14.

Regras que não mudam:
- Você não envia sozinha: quando o Wes pedir para mandar ou responder alguém (ou quando uma resposta for claramente necessária), prepare um cartão de envio. O Wes revisa e aperta "Enviar" no chat, e a mensagem sai pelo WhatsApp comercial (pela Evolution, sem usar as telas). Não use as telas para enviar.
- Formato do cartão (um por mensagem, exatamente assim; o número só com dígitos, com DDI 55 e DDD, ou o identificador que aparece nas conversas da Evolution):
[[enviar para="5511999998888" nome="Nome do contato"]]
texto da mensagem
[[/enviar]]
- Se não souber o número, procure nas conversas da Evolution ou no WhatsApp Web da tela; se não achar, pergunte ao Wes. Nunca diga que enviou: diga que está pronto para ele apertar Enviar.
- Mensagens sugeridas: curtas, simpáticas, no tom de WhatsApp, sem inventar preço, promoção ou horário que não aparecem nos dados.
- Priorize quem está esperando resposta (o cliente falou por último), do mais antigo para o mais novo.
- Responda em português do Brasil. Para cada pessoa, um bloco curto separado por linha em branco: **nome (número)**, por que agir agora, e a mensagem sugerida numa linha própria começando com "Mensagem:".

''' + TELAS_REGRAS + '''
- Para ler uma conversa no WhatsApp Web: usar_tela com tela "whatsapp", acao "clicar" e alvo o nome do contato ou o número dele na lista (1 = a primeira conversa). A resposta já traz as mensagens.'''
    prompt = '''=Agora: {{ $json.agora }}

{{ $json.whatsappSecao }}Telas agora:
{{ $json.telas }}

Instruções permanentes do Wes (siga sempre):
{{ $json.memorias }}

Conversa recente com você:
{{ $json.historico }}

Pedido de {{ $('Preparar').first().json.quem }}:
{{ $('Preparar').first().json.texto }}'''
    agente_ia(f, 'Ana pensa', 'Cérebro da Ana', sistema, prompt, [1540, 0], [ver_telas, usar_tela('ana'), lembrar('ana'), avisar_wes('ana')])
    f.link('Montar contexto', 'Escolher cérebro')
    code(f, 'Ler resposta', PARADA_JS + '''
return [{ json: { resposta: parou ? textoParou : String($json.output || $json.text || '').trim() || 'Não consegui escrever uma resposta agora.' } }];
''', [1820, 0])
    f.link('Ana pensa', 'Ler resposta')
    fim_agente(f, 'Ler resposta', 2040)
    f.save('agente-ana.json')


# ---------------------------------------------------------------- Carla
def abekyo_validar(f, pos):
    return ferramenta_http(
        f, 'abekyo_validar', 'Confere (sem gastar nada) se um projeto de vídeo do Abekyo está certo. Devolve erros, avisos e a duração.',
        'POST', f'{ABEKYO_N8N}/api/project/validate', pos, json_body='{projeto}',
        placeholders=[('projeto', 'o projeto de vídeo inteiro, em JSON, no formato do Abekyo', 'json')])


def abekyo_renderizar(f, pos):
    return ferramenta_http(
        f, 'abekyo_renderizar', 'Renderiza o projeto de vídeo no Abekyo e devolve o progresso; a última linha traz o videoUrl do MP4 pronto. Valide antes.',
        'POST', f'{ABEKYO_N8N}/api/render', pos, json_body='{projeto}',
        placeholders=[('projeto', 'o projeto de vídeo inteiro, em JSON, no formato do Abekyo', 'json')])


IMAGENS_URL = 'https://image.pollinations.ai/prompt/'  # gerador de imagens grátis, sem chave


def criar_imagem(f, pos):
    return ferramenta_http(
        f, 'criar_imagem', 'Cria uma imagem nova a partir de uma descrição (em inglês fica melhor) e já coloca no editor de vídeo. '
        'Devolve o endereço /uploads/... para usar como imageUrl no projeto e para mostrar na tela.',
        'POST', f'{N8N_INTERNO}/webhook/escritorio/carla-imagem', pos,
        corpo=[{'name': 'descricao', 'valueProvider': 'modelRequired'}, {'name': 'formato', 'valueProvider': 'modelOptional'}],
        placeholders=[('descricao', 'descrição detalhada da imagem: o que aparece, estilo, cores, luz; sem texto escrito na imagem', 'string'),
                      ('formato', 'quadrado, retrato (carrossel do Instagram, 1080x1350), story (1080x1920) ou paisagem (1920x1080)', 'string')])


def carla_imagens(f):
    # a ferramenta criar_imagem chama este caminho: gera a imagem e manda para o editor (Abekyo), que devolve o /uploads/...
    webhook(f, 'Pedido de imagem', 'escritorio/carla-imagem', 'POST', [0, 600])
    code(f, 'Montar imagem', '''
const b = $json.body || {};
const tam = { quadrado: [1080, 1080], retrato: [1080, 1350], story: [1080, 1920], paisagem: [1920, 1080] };
const f = String(b.formato || 'retrato').toLowerCase();
const [w, h] = tam[Object.keys(tam).find(k => f.includes(k)) || 'retrato'];
const descricao = String(b.descricao || '').trim().slice(0, 900) || 'cute happy dog at a dog daycare, bright, photo';
return [{ json: { descricao, url: ''' + json.dumps(IMAGENS_URL) + ''' + encodeURIComponent(descricao) + `?width=${w}&height=${h}&nologo=true&seed=${Math.floor(Math.random() * 1e9)}` } }];
''', [220, 600])
    f.add('Gerar a imagem', 'n8n-nodes-base.httpRequest', 4.2, {'url': '={{ $json.url }}', 'options': {
        'timeout': 120000, 'response': {'response': {'responseFormat': 'file', 'outputPropertyName': 'data'}}}}, [440, 600],
        onError='continueErrorOutput', retryOnFail=True, maxTries=2)
    f.add('Mandar a imagem para o editor', 'n8n-nodes-base.httpRequest', 4.2, {
        'method': 'POST', 'url': f'{ABEKYO_N8N}/api/upload', 'sendBody': True, 'contentType': 'multipart-form-data',
        'bodyParameters': {'parameters': [{'parameterType': 'formBinaryData', 'name': 'file', 'inputDataFieldName': 'data'}]},
        'options': {'timeout': 60000}}, [660, 560], onError='continueErrorOutput')
    respond(f, 'Imagem pronta', '''={{ JSON.stringify({ ok: true, imageUrl: $json.url, mostrar: ''' + json.dumps(ABEKYO_TELA) + ''' + $json.url, descricao: $('Montar imagem').first().json.descricao }) }}''', [880, 540])
    respond(f, 'Gerador falhou', '''={{ JSON.stringify({ ok: false, erro: 'o gerador de imagens (pollinations.ai) não respondeu agora: ' + String(($json.error && ($json.error.message || $json.error)) || 'erro').slice(0, 200) + '. Tente de novo daqui a pouco ou com outra descrição.' }) }}''', [660, 760])
    respond(f, 'Editor falhou', '''={{ JSON.stringify({ ok: false, erro: 'a imagem foi criada, mas o editor de vídeo (Abekyo, porta 3000) não guardou: ' + String(($json.error && ($json.error.message || $json.error)) || 'erro').slice(0, 200) + '. Ele está ligado?' }) }}''', [880, 720])
    f.chain('Pedido de imagem', 'Montar imagem', 'Gerar a imagem', 'Mandar a imagem para o editor', 'Imagem pronta')
    f.link('Gerar a imagem', 'Gerador falhou', out=1)
    f.link('Mandar a imagem para o editor', 'Editor falhou', out=1)


def carla():
    f = Flow('Escritório · Carla (Conteúdo e vídeos)', 'escCarla00000001')
    carla_imagens(f)
    inicio_agente(f, 'carla', f'''const ABEKYO_TELA = '{ABEKYO_TELA}';   // o editor de vídeo como o Chrome do escritório enxerga
const abekyo = ABEKYO_TELA;''')
    code(f, 'Montar contexto', CONTEXTO_COMUM + '''
return [{ json: { memorias, historico, equipe, agora, mural, telas, abekyo: $('Preparar').first().json.abekyo } }];
''', [1100, 0])
    f.chain('Avisar: trabalhando', 'Ler estado do escritório', 'Montar contexto')
    sistema = '''Você é a Carla, agente de conteúdo e vídeos do Cantinho do Au Au (creche, hotel e banho e tosa de cães, em São Paulo) e da Mentoria Creche Milionária, do Wes. Seu computador é o PC 3 (pc2).

O que você faz:
- Carrosséis de Instagram: título forte no primeiro slide, um texto curto por slide (6 a 10 slides), legenda e hashtags.
- Roteiros de Reels e vídeos curtos: gancho nos 3 primeiros segundos, cenas com texto na tela e narração, chamada para ação no fim.
- Vídeos no editor Abekyo (Remotion), que fica aberto no seu PC (pc2, "PC 3"):
  1. Monte o projeto em JSON no formato do Abekyo: {"clips": [{"plotName": "Cena 1", "text": "...", "imageUrl": "", "audioUrl": "", "duration": 3, "index": 0, "transitionType": "fade"}], "subtitles": [{"id": "s1", "text": "...", "startTime": 0, "endTime": 3, "position": "bottom", "fontSize": 5, "color": "#ffffff", "align": "center"}], "resolution": "1080p", "aspectRatio": "16:9"}.
     Use imageUrl só com endereços /uploads/...: os que o Wes passar ou os que você criar com criar_imagem; sem imagem a cena fica com fundo preto e a legenda por cima.
  2. Confira com abekyo_validar e corrija os erros.
  3. Renderize com abekyo_renderizar. A última linha traz o "videoUrl".
  4. Mostre o vídeo no seu PC: usar_tela com tela "pc2", acao "abrir" e alvo o endereço do editor (está em "Editor de vídeo" no pedido) + o videoUrl, por exemplo http://localhost:3000/uploads/output/arquivo.mp4.
  5. Responda com o endereço do vídeo e o projeto em JSON, para poder ajustar depois.
- Quando o Wes pedir uma edição, ajuste o último projeto (está na conversa) e renderize de novo. Ele também pode editar à mão no editor aberto no seu PC.
- Imagens: você mesma cria com a ferramenta criar_imagem (uma por slide ou cena, descrição em inglês, detalhada, sem texto escrito na imagem; o texto vai no slide/legenda). Quando pedirem imagens, crie na hora; não peça para o Wes mandar arquivos. Mostre as imagens no seu PC (usar_tela, tela "meu pc", acao "abrir", alvo o endereço "mostrar" que a ferramenta devolve) e liste os endereços /uploads/... na resposta.

Regras:
- Responda em português do Brasil. Tom do Cantinho: carinhoso, leve e confiável. Sem prometer preço, promoção ou horário que o Wes não passou.

''' + TELAS_REGRAS
    prompt = '''=Agora: {{ $json.agora }}

Editor de vídeo (Abekyo) no Chrome do escritório: {{ $json.abekyo }}

Telas agora:
{{ $json.telas }}

Mural de avisos:
{{ $json.mural }}

Instruções permanentes do Wes (siga sempre):
{{ $json.memorias }}

Conversa recente com você:
{{ $json.historico }}

Pedido de {{ $('Preparar').first().json.quem }}:
{{ $('Preparar').first().json.texto }}'''
    agente_ia(f, 'Carla pensa', 'Cérebro da Carla', sistema, prompt, [1320, 0], [ver_telas, usar_tela('carla'), lembrar('carla'), avisar_wes('carla'), abekyo_validar, abekyo_renderizar, criar_imagem])
    f.link('Montar contexto', 'Escolher cérebro')
    code(f, 'Ler resposta', PARADA_JS + '''
return [{ json: { resposta: parou ? textoParou : String($json.output || $json.text || '').trim() || 'Não consegui escrever uma resposta agora.' } }];
''', [1820, 0])
    f.link('Carla pensa', 'Ler resposta')
    fim_agente(f, 'Ler resposta', 2040)
    f.save('agente-carla.json')


# ---------------------------------------------------------------- Painel comercial (segunda tela da Ana)
# Régua de follow-up ao vivo (conversas da Evolution) e os envios pelo Telegram: Mari (SDR, todo dia), Gustavo (vendedor,
# todo dia), Rosângela (só caso crítico) e Wes (por último). O Wes confere e envia no painel; o envio diário sozinho
# só acontece se ele ligar no painel.
TABELA_CFG = 'escritorio_config'
COLUNAS_CFG = ['chave', 'valor']
PAINEL_CFG = """
// ===== configuração (o instalador preenche) =====
const EVOLUTION_URL = '';
const EVOLUTION_KEY = '';
const INSTANCIA = 'cantinho-comercial';
const CODIGO_ENVIO = '';
// =================================================
"""
LER_CFG_JS = """
const cfg = {};
$('Ler a configuração').all().map(i => i.json).filter(r => r && r.chave).sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt) || a.id - b.id)
  .forEach(r => { cfg[r.chave] = r.valor || ''; });
"""
PESSOAS = {'mari': 'Mari', 'gustavo': 'Gustavo', 'rosangela': 'Rosângela', 'wes': 'Wes'}
MONTAR_PAINEL_JS = LER_CFG_JS + """
const P = $('Preparar o painel').first().json;
const r = $('Conversas da Evolution').first().json || {};
const lista = Array.isArray(r.body) ? r.body : Array.isArray(r.body && r.body.chats) ? r.body.chats : [];
const estadoZap = String(((($('Estado do WhatsApp').first().json || {}).body || {}).instance || {}).state || '');
const envios = $('Envios recentes').all().map(i => i.json).filter(x => x && x.agente === 'telegram')
  .map(x => ({ para: x.de, texto: x.texto, t: x.createdAt, status: x.status || 'enviado' }));
const textoDe = m => { m = m || {}; return m.conversation || (m.extendedTextMessage || {}).text || (m.imageMessage || {}).caption || (m.videoMessage || {}).caption
  || (m.audioMessage ? '[áudio]' : m.imageMessage ? '[imagem]' : m.documentMessage ? '[documento]' : m.stickerMessage ? '[figurinha]' : ''); };
const CRITICO = /reembols|cancel|reclama|machuc|doente|ferid|sangr|vomit|absurd|p[eé]ssim|procon|devolu|estorno|insatisf/i;
const agora = Date.now() / 1000;
const regua = { D0: [], R1: [], R2: [], R3: [], R4: [], R5: [] }, esperando = [], criticos = [];
for (const c of lista) {
  const jid = String(c.remoteJid || c.id || '');
  if (!jid || /@g\\.us|@broadcast|@newsletter/.test(jid)) continue;
  const lm = c.lastMessage || null;
  const ts = Number(lm && lm.messageTimestamp) || (Date.parse(c.updatedAt) / 1000) || 0;
  if (!ts) continue;
  const dias = (agora - ts) / 86400;
  if (dias > 30) continue;
  const lead = { nome: c.pushName || (lm && lm.pushName) || jid.split('@')[0], numero: jid.endsWith('@s.whatsapp.net') ? jid.split('@')[0] : jid,
                 ultimo: textoDe(lm && lm.message).replace(/\\s+/g, ' ').slice(0, 140), dias: Math.floor(dias), horas: Math.floor(dias * 24), t: new Date(ts * 1000).toISOString() };
  if (lm && lm.key && lm.key.fromMe) {
    // a régua conta desde a nossa mensagem que ficou sem resposta; se o lead responde, ele sai da régua
    const etapa = dias >= 14 ? 'R5' : dias >= 7 ? 'R4' : dias >= 4 ? 'R3' : dias >= 2 ? 'R2' : dias >= 1 ? 'R1' : 'D0';
    regua[etapa].push(Object.assign({ etapa }, lead));
  } else if (lm && lm.key && lm.key.fromMe === false) {
    lead.critico = lead.horas >= 24 || CRITICO.test(lead.ultimo);
    lead.motivo = CRITICO.test(lead.ultimo) ? 'assunto delicado na última mensagem' : lead.horas >= 24 ? 'sem resposta há mais de 24h' : '';
    esperando.push(lead);
    if (lead.critico) criticos.push(lead);
  }
}
Object.values(regua).forEach(l => l.sort((a, b) => b.dias - a.dias));
esperando.sort((a, b) => b.horas - a.horas);
// mensagens de cada pessoa (o Wes confere e pode mudar antes de enviar)
const linha = l => `• ${l.nome}${/^\\d+$/.test(l.numero) ? ' (' + l.numero + ')' : ''} — ${l.horas < 24 ? l.horas + 'h' : l.dias + ' dia(s)'}${l.ultimo ? ': "' + l.ultimo.slice(0, 80) + '"' : ''}`;
const hoje = new Date().toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo', weekday: 'long', day: '2-digit', month: '2-digit' });
const followups = ['R1', 'R2', 'R3', 'R4', 'R5'].filter(k => regua[k].length).map(k => `${k} (${regua[k].length}):\\n` + regua[k].slice(0, 8).map(linha).join('\\n')).join('\\n\\n');
const mensagens = {
  mari: `Bom dia, Mari! Comercial de ${hoje}\\n\\n` + (esperando.length ? `Esperando resposta (${esperando.length}):\\n${esperando.slice(0, 15).map(linha).join('\\n')}` : 'Ninguém esperando resposta agora.')
    + (followups ? `\\n\\nFollow-ups do dia pela régua:\\n${followups}` : '\\n\\nNenhum follow-up vencido hoje.')
    + '\\n\\nLembre de confirmar as avaliações de amanhã, remarcar quem faltou e registrar tudo no CRM.',
  gustavo: `Bom dia, Gustavo! Resumo de ${hoje}\\n\\n` + (criticos.length ? `Críticos (${criticos.length}):\\n${criticos.slice(0, 10).map(l => linha(l) + (l.motivo ? ' · ' + l.motivo : '')).join('\\n')}` : 'Nenhum caso crítico agora.')
    + `\\n\\nNa régua: ${Object.entries(regua).map(([k, l]) => k + ' ' + l.length).join(' · ')}.\\nConfira as avaliações do dia e lance o fechamento no CRM (presença e faturamento).`,
  rosangela: criticos.length ? `Rosângela, casos críticos no comercial (${criticos.length}):\\n${criticos.slice(0, 10).map(l => linha(l) + (l.motivo ? ' · ' + l.motivo : '')).join('\\n')}` : '',
  wes: '',
};
// Wes por último: crítico ainda aberto 20h depois do aviso à Rosângela, ou WhatsApp desconectado
const avisoRos = envios.filter(e => e.para === 'rosangela').map(e => Date.parse(e.t)).sort((a, b) => b - a)[0] || 0;
const alertas = [];
if (avisoRos && Date.now() - avisoRos > 20 * 3600000 && criticos.length) alertas.push(`${criticos.length} caso(s) crítico(s) ainda aberto(s) 20h depois do aviso à Rosângela:\\n${criticos.slice(0, 8).map(linha).join('\\n')}`);
if (P.evolutionOk && estadoZap && estadoZap !== 'open') alertas.push(`Alerta de conexão: o WhatsApp comercial está "${estadoZap}" (desconectado). Abra o escritório para ler o QR code.`);
if (alertas.length) mensagens.wes = 'Wes, atenção:\\n\\n' + alertas.join('\\n\\n');
const pessoas = """ + json.dumps(PESSOAS, ensure_ascii=False) + """;
const telegram = { configurado: !!cfg.telegram_token, auto: cfg.auto === 'sim', pessoas: Object.fromEntries(Object.keys(pessoas).map(k => [k, { nome: pessoas[k], chat: cfg['chat_' + k] || '' }])) };
"""


def painel():
    f = Flow('Escritório · Painel comercial', 'escPainel0000001')

    def ler_dados(prefixo, x, y, gatilho):
        # config -> envios recentes -> conversas da Evolution -> estado do WhatsApp -> montar
        code(f, 'Preparar o painel' + prefixo, PAINEL_CFG + """
return [{ json: { evolutionOk: !!(EVOLUTION_URL && EVOLUTION_KEY), chats: `${EVOLUTION_URL}/chat/findChats/${INSTANCIA}`, estado: `${EVOLUTION_URL}/instance/connectionState/${INSTANCIA}`, key: EVOLUTION_KEY } }];
""", [x, y])
        criar_tabela(f, 'Garantir a configuração' + prefixo, [x + 220, y], nome=TABELA_CFG, colunas=COLUNAS_CFG)
        tabela(f, 'Ler a configuração' + prefixo, [x + 440, y], nome=TABELA_CFG, operation='get', returnAll=True)
        f.nodes[-1].update(alwaysOutputData=True, executeOnce=True)
        criar_tabela(f, 'Garantir o registro' + prefixo, [x + 660, y])
        tabela(f, 'Envios recentes' + prefixo, [x + 880, y], operation='get', limit=40, orderBy=True, orderByColumn='createdAt', orderByDirection='DESC',
               matchType='allConditions', filters={'conditions': [{'keyName': 'agente', 'condition': 'eq', 'keyValue': 'telegram'}]})
        f.nodes[-1].update(alwaysOutputData=True, executeOnce=True)
        http_json(f, 'Conversas da Evolution' + prefixo, 'POST', "={{ $('Preparar o painel" + prefixo + "').first().json.chats }}", '={{ JSON.stringify({}) }}',
                  [x + 1100, y], headers=[('apikey', "={{ $('Preparar o painel" + prefixo + "').first().json.key }}")], timeout=20000)
        f.nodes[-1]['executeOnce'] = True
        http_json(f, 'Estado do WhatsApp' + prefixo, 'GET', "={{ $('Preparar o painel" + prefixo + "').first().json.estado }}", None,
                  [x + 1320, y], headers=[('apikey', "={{ $('Preparar o painel" + prefixo + "').first().json.key }}")], timeout=10000)
        f.nodes[-1]['executeOnce'] = True
        f.chain(gatilho, 'Preparar o painel' + prefixo, 'Garantir a configuração' + prefixo, 'Ler a configuração' + prefixo, 'Garantir o registro' + prefixo,
                'Envios recentes' + prefixo, 'Conversas da Evolution' + prefixo, 'Estado do WhatsApp' + prefixo)

    def js(prefixo, texto):  # os nomes dos nós de cada caminho levam o sufixo do caminho
        for nome in ['Preparar o painel', 'Ler a configuração', 'Envios recentes', 'Conversas da Evolution', 'Estado do WhatsApp']:
            texto = texto.replace(f"$('{nome}')", f"$('{nome}{prefixo}')")
        return texto

    # ---- 1. o painel pede os dados
    webhook(f, 'Painel pede os dados', 'escritorio/comercial', 'GET', [0, 0])
    ler_dados('', 220, 0, 'Painel pede os dados')
    code(f, 'Montar o painel', js('', MONTAR_PAINEL_JS) + """
return [{ json: { atualizado: new Date().toISOString(), whatsapp: !P.evolutionOk ? 'sem Evolution' : estadoZap || 'sem resposta', conversas: lista.length,
  regua, esperando: esperando.slice(0, 60), criticos, mensagens, telegram, envios: envios.slice(0, 20) } }];
""", [1760, 0])
    respond(f, 'Mandar o painel', '={{ JSON.stringify($json) }}', [1980, 0])
    f.chain('Estado do WhatsApp', 'Montar o painel', 'Mandar o painel')

    # ---- 2. o Wes configura o Telegram (token do bot, quem é quem, envio diário)
    webhook(f, 'Painel muda a configuração', 'escritorio/comercial-config', 'POST', [0, 400])
    code(f, 'Conferir a configuração', PAINEL_CFG + """
const b = $json.body || {};
const PODE = ['telegram_token', 'chat_mari', 'chat_gustavo', 'chat_rosangela', 'chat_wes', 'auto'];
if (!CODIGO_ENVIO || b.codigo !== CODIGO_ENVIO) return [{ json: { erro: 'pedido sem o código do escritório' } }];
if (!PODE.includes(b.chave)) return [{ json: { erro: 'configuração desconhecida: ' + b.chave } }];
return [{ json: { chave: b.chave, valor: String(b.valor == null ? '' : b.valor).trim().slice(0, 200) } }];
""", [220, 400])
    f.add('Configuração ok?', 'n8n-nodes-base.if', 2.2, {'conditions': {
        'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
        'conditions': [{'id': nid(), 'leftValue': '={{ $json.erro }}', 'rightValue': '', 'operator': {'type': 'string', 'operation': 'empty', 'singleValue': True}}],
        'combinator': 'and'}, 'options': {}}, [440, 400])
    criar_tabela(f, 'Garantir a configuração (mudar)', [660, 360], nome=TABELA_CFG, colunas=COLUNAS_CFG)
    code(f, 'Linha da configuração', "return [{ json: { chave: $('Conferir a configuração').first().json.chave, valor: $('Conferir a configuração').first().json.valor } }];", [880, 360])
    tabela(f, 'Guardar a configuração', [1100, 360], nome=TABELA_CFG, operation='insert',
           columns={'mappingMode': 'autoMapInputData', 'value': {}, 'matchingColumns': [], 'schema': []}, options={})
    respond(f, 'Configuração guardada', '={{ JSON.stringify({ ok: true }) }}', [1320, 360])
    respond(f, 'Configuração recusada', '={{ JSON.stringify({ ok: false, erro: $json.erro }) }}', [660, 500])
    f.chain('Painel muda a configuração', 'Conferir a configuração', 'Configuração ok?')
    f.link('Configuração ok?', 'Garantir a configuração (mudar)', out=0)
    f.link('Configuração ok?', 'Configuração recusada', out=1)
    f.chain('Garantir a configuração (mudar)', 'Linha da configuração', 'Guardar a configuração', 'Configuração guardada')

    # ---- 3. o Wes aperta "Enviar" para alguém (ou "Descobrir IDs" do Telegram)
    webhook(f, 'Painel pede um envio', 'escritorio/telegram', 'POST', [0, 700])
    criar_tabela(f, 'Garantir a configuração (envio)', [220, 700], nome=TABELA_CFG, colunas=COLUNAS_CFG)
    tabela(f, 'Ler a configuração (envio)', [440, 700], nome=TABELA_CFG, operation='get', returnAll=True)
    f.nodes[-1].update(alwaysOutputData=True, executeOnce=True)
    code(f, 'Conferir o envio', PAINEL_CFG + LER_CFG_JS.replace("$('Ler a configuração')", "$('Ler a configuração (envio)')") + """
const b = $('Painel pede um envio').first().json.body || {};
const pessoas = """ + json.dumps(PESSOAS, ensure_ascii=False) + """;
let erro = '';
if (!CODIGO_ENVIO || b.codigo !== CODIGO_ENVIO) erro = 'pedido sem o código do escritório';
else if (!cfg.telegram_token) erro = 'falta o token do bot do Telegram (configure no painel)';
const acao = b.acao === 'ids' ? 'ids' : 'enviar';
const para = String(b.para || ''), chat = cfg['chat_' + para] || '', texto = String(b.texto || '').trim().slice(0, 3900);
if (!erro && acao === 'enviar') {
  if (!pessoas[para]) erro = 'destinatário desconhecido: ' + para;
  else if (!chat) erro = `falta o ID do Telegram de ${pessoas[para]} (configure no painel)`;
  else if (!texto) erro = 'mensagem vazia';
}
const base = 'https://api.telegram.org/bot' + cfg.telegram_token;
return [{ json: { erro, acao, para, nome: pessoas[para] || para, chat, texto,
  url: acao === 'ids' ? base + '/getUpdates?limit=100' : base + '/sendMessage', corpo: { chat_id: chat, text: texto, disable_web_page_preview: true } } }];
""", [660, 700])
    f.add('Envio ok?', 'n8n-nodes-base.if', 2.2, {'conditions': {
        'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
        'conditions': [{'id': nid(), 'leftValue': '={{ $json.erro }}', 'rightValue': '', 'operator': {'type': 'string', 'operation': 'empty', 'singleValue': True}}],
        'combinator': 'and'}, 'options': {}}, [880, 700])
    respond(f, 'Envio recusado', '={{ JSON.stringify({ ok: false, erro: $json.erro }) }}', [1100, 860])
    http_json(f, 'Chamar o Telegram', 'POST', '={{ $json.url }}', '={{ JSON.stringify($json.acao === "ids" ? {} : $json.corpo) }}', [1100, 660], timeout=20000)
    code(f, 'Resposta do Telegram', """
const c = $('Conferir o envio').first().json, r = $json, body = r.body || {};
const ok = (r.statusCode || 0) >= 200 && (r.statusCode || 0) < 300 && body.ok !== false;
const erro = ok ? '' : 'o Telegram recusou: ' + (body.description || r.statusCode || 'sem resposta');
if (c.acao === 'ids') {
  // quem já mandou mensagem para o bot aparece aqui (cada pessoa precisa mandar um "oi" para o bot uma vez)
  const chats = {};
  for (const u of (body.result || [])) { const m = u.message || u.edited_message || u.channel_post || {}; const ch = m.chat; if (ch) chats[ch.id] = [ch.first_name, ch.last_name, ch.title, ch.username && '@' + ch.username].filter(Boolean).join(' '); }
  return [{ json: { ok, erro, ids: Object.entries(chats).map(([id, nome]) => ({ id, nome })) } }];
}
return [{ json: { ok, erro, para: c.para, nome: c.nome, texto: c.texto } }];
""", [1320, 660])
    f.add('Guardar no histórico?', 'n8n-nodes-base.if', 2.2, {'conditions': {
        'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
        'conditions': [{'id': nid(), 'leftValue': '={{ $json.ok && !$json.ids }}', 'rightValue': '', 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}],
        'combinator': 'and'}, 'options': {}}, [1540, 660])
    code(f, 'Linha do envio', "const c = $json; return [{ json: { agente: 'telegram', de: c.para, texto: c.texto, status: 'enviado', evento: 'Telegram para ' + c.nome } }];", [1760, 600])
    tabela(f, 'Guardar o envio', [1980, 600], operation='insert',
           columns={'mappingMode': 'autoMapInputData', 'value': {}, 'matchingColumns': [], 'schema': []}, options={})
    respond(f, 'Responder o envio', "={{ JSON.stringify($('Resposta do Telegram').first().json) }}", [2200, 660])
    f.chain('Painel pede um envio', 'Garantir a configuração (envio)', 'Ler a configuração (envio)', 'Conferir o envio', 'Envio ok?')
    f.link('Envio ok?', 'Chamar o Telegram', out=0)
    f.link('Envio ok?', 'Envio recusado', out=1)
    f.chain('Chamar o Telegram', 'Resposta do Telegram', 'Guardar no histórico?')
    f.link('Guardar no histórico?', 'Linha do envio', out=0)
    f.link('Guardar no histórico?', 'Responder o envio', out=1)
    f.chain('Linha do envio', 'Guardar o envio', 'Responder o envio')

    # ---- 4. envio diário sozinho (só se o Wes ligou no painel): Mari e Gustavo todo dia; Rosângela e Wes quando houver algo
    f.add('Todo dia às 8h30', 'n8n-nodes-base.scheduleTrigger', 1.2, {'rule': {'interval': [{'field': 'cronExpression', 'expression': '30 8 * * *'}]}}, [0, 1100])
    ler_dados(' (diário)', 220, 1100, 'Todo dia às 8h30')
    code(f, 'Quem recebe hoje', js(' (diário)', MONTAR_PAINEL_JS) + """
if (!telegram.auto || !cfg.telegram_token) return [];
const base = 'https://api.telegram.org/bot' + cfg.telegram_token + '/sendMessage';
return Object.keys(pessoas).filter(k => mensagens[k] && telegram.pessoas[k].chat)
  .map(k => ({ json: { url: base, para: k, nome: pessoas[k], texto: mensagens[k], corpo: { chat_id: telegram.pessoas[k].chat, text: mensagens[k].slice(0, 3900), disable_web_page_preview: true } } }));
""", [1760, 1100])
    http_json(f, 'Enviar o diário', 'POST', '={{ $json.url }}', '={{ JSON.stringify($json.corpo) }}', [1980, 1100], timeout=20000)
    code(f, 'Linhas do diário', """
const pedidos = $('Quem recebe hoje').all();
return $input.all().map((it, i) => { const p = pedidos[i].json, ok = (it.json.statusCode || 0) < 300 && (it.json.body || {}).ok !== false;
  return { json: { agente: 'telegram', de: p.para, texto: p.texto, status: ok ? 'enviado (diário)' : 'falhou', evento: 'Telegram diário para ' + p.nome } }; });
""", [2200, 1100])
    tabela(f, 'Guardar o diário', [2420, 1100], operation='insert',
           columns={'mappingMode': 'autoMapInputData', 'value': {}, 'matchingColumns': [], 'schema': []}, options={})
    f.chain('Estado do WhatsApp (diário)', 'Quem recebe hoje', 'Enviar o diário', 'Linhas do diário', 'Guardar o diário')
    f.save('painel-comercial.json')


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    central(); fabio(); ana(); carla(); painel()
    with open(os.path.join(OUT, 'versao.txt'), 'w', encoding='utf-8') as f:
        f.write(VERSAO + '\n')
    # o escritório leva a mesma versão, para avisar quando o n8n estiver com fluxos antigos
    html = os.path.join(OUT, '..', 'escritorio-3d.html')
    texto = open(html, encoding='utf-8').read()
    novo = re.sub(r"const VERSAO = '[^']*';", f"const VERSAO = '{VERSAO}';", texto)
    if novo != texto:
        open(html, 'w', encoding='utf-8').write(novo)
    print('fluxos gerados em', os.path.normpath(OUT))
