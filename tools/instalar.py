# Instala os agentes do escritório no n8n deste PC (dois cliques em instalar.bat). Não faz perguntas.
#
#   python tools/instalar.py            instala ou atualiza tudo e abre o escritório
#   python tools/instalar.py --ligar    liga o que precisa e atualiza os agentes se a pasta for nova (usado pelo abrir-escritorio.bat)
#
# O que ele faz sozinho:
#   1. liga o Docker Desktop e o n8n (no Docker ou instalado no Windows)
#   2. cérebro dos agentes: liga o Ollama, registra os modelos da nuvem do Ollama (pede o login do Ollama se precisar)
#      e monta a lista de cérebros: se um falhar ou acabar o limite, o agente troca sozinho para o próximo.
#      Sem Ollama, usa o Gemini que já estiver no n8n. Opções: --modelo=nome (vai primeiro na lista), --gemini
#   3. WhatsApp: sobe a Evolution do escritório no Docker (servidor/evolution) e mostra o QR code para conectar
#   4. importa e ativa os 4 fluxos da pasta n8n/ (Central, Fábio, Ana e Carla), reinicia o n8n e testa
#   5. liga o editor de vídeo da Carla (pasta abekyo-editor, http://localhost:3000; npm install na primeira vez)
#   6. grava o endereço do n8n para o escritório (escritorio-config.js)
import json, os, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLUXOS = [('escritorio-central.json', 'escCentral000001'), ('agente-fabio.json', 'escFabio00000001'), ('agente-ana.json', 'escAna0000000001'),
          ('agente-carla.json', 'escCarla00000001'), ('painel-comercial.json', 'escPainel0000001')]
ABEKYO_PORTA = 3000  # editor de vídeo da Carla (abekyo-editor, "npm run dev")
INSTANCIA_PADRAO = 'cantinho-comercial'
VERSAO_MINIMA = (1, 113)  # tabelas de dados do n8n
# onde o Docker costuma ficar no Windows quando o comando "docker" não está no caminho
PF, LAD = os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('LOCALAPPDATA', '')
DOCKER_EXES = [os.path.join(PF, r'Docker\Docker\resources\bin\docker.exe'), os.path.join(LAD, r'Programs\Docker\Docker\resources\bin\docker.exe'),
               r'C:\ProgramData\DockerDesktop\version-bin\docker.exe']
DOCKER_DESKTOPS = [os.path.join(PF, r'Docker\Docker\Docker Desktop.exe'), os.path.join(LAD, r'Programs\Docker\Docker\Docker Desktop.exe')]
DOCKER = shutil.which('docker') or next((x for x in DOCKER_EXES if os.path.exists(x)), None)

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def passo(msg): print(f'\n== {msg}', flush=True)
def ok(msg): print(f'   ok: {msg}', flush=True)
def aviso(msg): print(f'   atenção: {msg}', flush=True)


def parar(msg):
    print(f'\n   NÃO DEU PARA CONTINUAR: {msg}\n', flush=True)
    if sys.stdin.isatty():
        input('Aperte Enter para fechar...')
    sys.exit(1)


def docker(*args, check=True):
    try:
        r = subprocess.run([DOCKER or 'docker', *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    except FileNotFoundError:
        raise RuntimeError('comando "docker" não encontrado')
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or f'docker {" ".join(args)} falhou')
    return r


def http(url, headers=None, timeout=5):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', 'replace')


# ---------------------------------------------------------------- Docker e containers
def ligar_docker():
    """Liga o Docker Desktop se precisar. Devolve False quando o Docker não está instalado neste PC."""
    global DOCKER
    passo('Docker')
    desktop = next((x for x in DOCKER_DESKTOPS if os.path.exists(x)), None)
    if not DOCKER and not desktop:
        ok('o Docker Desktop não está instalado neste PC: procurando o n8n instalado direto no Windows')
        return False
    if DOCKER and docker('info', check=False).returncode == 0:
        ok('Docker ligado'); return True
    if not desktop and shutil.which('n8n'):
        ok('o Docker não está ligado e não achei o Docker Desktop: usando o n8n instalado direto no Windows')
        return False
    if desktop:
        print('   ligando o Docker Desktop (pode levar 1 ou 2 minutos)...', flush=True)
        subprocess.Popen([desktop])
    for _ in range(90 if desktop else 5):
        time.sleep(2)
        DOCKER = DOCKER or shutil.which('docker') or next((x for x in DOCKER_EXES if os.path.exists(x)), None)
        if DOCKER and docker('info', check=False).returncode == 0:
            ok('Docker ligado'); return True
    parar('o Docker não ligou. Abra o Docker Desktop, espere aparecer "Engine running" e rode de novo.')


def containers():
    r = docker('ps', '-a', '--format', '{{.Names}}\t{{.Image}}\t{{.State}}')
    lista = []
    for linha in r.stdout.splitlines():
        partes = linha.split('\t')
        if len(partes) >= 3:
            lista.append({'nome': partes[0], 'imagem': partes[1].lower(), 'estado': partes[2].lower()})
    return lista


def escolher(lista, palavra, evitar=()):
    achados = [c for c in lista if palavra in c['imagem'] and not any(e in c['imagem'] or e in c['nome'].lower() for e in evitar)]
    achados.sort(key=lambda c: (c['nome'].lower() != palavra, c['estado'] != 'running'))
    return achados[0] if achados else None


def inspecionar(nome):
    return json.loads(docker('inspect', nome).stdout)[0]


def ligar_grupo(c):
    """Liga o container e os outros do mesmo grupo do docker compose (banco, Evolution...)."""
    proj = (inspecionar(c['nome']).get('Config', {}).get('Labels') or {}).get('com.docker.compose.project')
    nomes = [c['nome']]
    if proj:
        r = docker('ps', '-a', '--filter', f'label=com.docker.compose.project={proj}', '--format', '{{.Names}}\t{{.State}}')
        nomes = [l.split('\t')[0] for l in r.stdout.splitlines() if l.strip()] or nomes
    parados = [n for n in nomes if docker('inspect', '-f', '{{.State.Running}}', n).stdout.strip() != 'true']
    if parados:
        print(f'   ligando: {", ".join(parados)}', flush=True)
        docker('start', *parados)
    return proj


def env_de(info):
    return dict(e.split('=', 1) for e in (info.get('Config', {}).get('Env') or []) if '=' in e)


def porta_no_pc(nome, interna):
    r = docker('port', nome, f'{interna}/tcp', check=False)
    m = re.search(r':(\d+)\s*$', r.stdout.strip().splitlines()[0]) if r.stdout.strip() else None
    return int(m.group(1)) if m else None


def esperar_n8n(porta, segundos=120):
    for _ in range(segundos // 2):
        try:
            if http(f'http://localhost:{porta}/healthz')[0] == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def n8n_local():
    """n8n instalado direto no Windows (npm), sem Docker: usa o comando n8n deste PC."""
    passo('n8n')
    cli = shutil.which('n8n')
    porta = 5678
    try:
        respondendo = http(f'http://localhost:{porta}/healthz')[0] == 200
    except Exception:
        respondendo = False
    if not cli:
        parar('não achei o Docker nem o comando "n8n" neste PC.' + (
            ' O n8n responde em http://localhost:5678, mas não sei como ele foi instalado: me mande um print de como você liga o n8n.'
            if respondendo else ' Como você liga o n8n normalmente? Ligue ele e rode de novo, ou me mande um print.'))
    if not respondendo:
        print('   ligando o n8n numa janela nova (deixe ela aberta)...', flush=True)
        if os.name == 'nt':
            # no "start" do Windows o primeiro texto entre aspas é o título da janela; o comando vem depois
            subprocess.Popen(f'start "n8n (deixe aberta)" "{cli}" start', shell=True)
        else:
            subprocess.Popen([cli, 'start'])
        if not esperar_n8n(porta, 180):
            parar('o n8n não respondeu em http://localhost:5678. Veja a janela do n8n.')
    ok(f'n8n ligado em http://localhost:{porta} (instalado no Windows: {cli})')
    try:
        lista = containers() if DOCKER else []  # a Evolution pode estar no Docker mesmo com o n8n fora dele
    except RuntimeError:
        lista = []
    return {'local': True, 'cli': cli, 'porta': porta, 'interna': porta, 'info': {}, 'lista': lista}


def pids_na_porta(porta):
    pids = set()
    if os.name == 'nt':
        r = subprocess.run(['netstat', '-ano', '-p', 'TCP'], capture_output=True, text=True, errors='replace')
        for linha in r.stdout.splitlines():
            partes = linha.split()
            if len(partes) >= 5 and partes[1].endswith(f':{porta}') and partes[3].upper() in ('LISTENING', 'ESCUTANDO'):
                pids.add(partes[4])
    else:
        if shutil.which('lsof'):
            pids.update(subprocess.run(['lsof', '-ti', f'tcp:{porta}', '-sTCP:LISTEN'], capture_output=True, text=True).stdout.split())
        elif shutil.which('ss'):
            pids.update(re.findall(r'pid=(\d+)', subprocess.run(['ss', '-ltnpH', f'sport = :{porta}'], capture_output=True, text=True).stdout))
    return [p for p in pids if p not in ('0', str(os.getpid()))]


def reiniciar_n8n_local(n):
    """Fecha o n8n deste PC e liga de novo (é assim que o n8n carrega os fluxos novos)."""
    print('   reiniciando o n8n para ligar os fluxos...', flush=True)
    for pid in pids_na_porta(n['porta']):
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', pid, '/T', '/F'], capture_output=True)
        else:
            try: os.kill(int(pid), 15)
            except Exception: pass
    for _ in range(30):  # espera o n8n antigo soltar a porta
        try: http(f'http://localhost:{n["porta"]}/healthz', timeout=2)
        except Exception: break
        time.sleep(1)
    if os.name == 'nt':
        subprocess.Popen(f'start "n8n (deixe aberta)" "{n["cli"]}" start', shell=True)
    else:
        subprocess.Popen([n['cli'], 'start'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return esperar_n8n(n['porta'], 180)


def ligar_n8n():
    if not ligar_docker():
        return n8n_local()
    passo('n8n')
    lista = containers()
    n8n = escolher(lista, 'n8n', evitar=('runner',))
    if not n8n:
        if shutil.which('n8n'):
            return n8n_local()
        parar('não achei o container do n8n no Docker. Ligue o n8n uma vez pelo Docker Desktop e rode de novo.')
    ligar_grupo(n8n)
    info = inspecionar(n8n['nome'])
    interna = int(env_de(info).get('N8N_PORT', '5678'))
    porta = porta_no_pc(n8n['nome'], interna) or interna
    if not esperar_n8n(porta):
        parar(f'o n8n não respondeu em http://localhost:{porta}. Veja o container "{n8n["nome"]}" no Docker Desktop.')
    ok(f'n8n ligado em http://localhost:{porta} (container "{n8n["nome"]}")')
    return {'container': n8n['nome'], 'porta': porta, 'interna': interna, 'info': info, 'lista': lista}


# ---------------------------------------------------------------- dentro do n8n
def n8n_cli(n, *args, check=True):
    for tentativa in range(6):  # o banco do n8n às vezes está ocupado (SQLITE_BUSY): espera e tenta de novo
        if n.get('local'):
            r = subprocess.run([n['cli'], *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
        else:
            r = docker('exec', '-u', 'node', n['container'], 'n8n', *args, check=False)
        if r.returncode == 0 or 'SQLITE_BUSY' not in (r.stderr or '') + (r.stdout or ''):
            break
        time.sleep(3)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or f'n8n {" ".join(args)} falhou')
    return r


def apagar_no_n8n(n, caminho):
    if n.get('local'):
        if os.path.exists(caminho): os.remove(caminho)
    else:
        docker('exec', '-u', 'root', n['container'], 'rm', '-rf', caminho, check=False)


def conferir_versao(n):
    out = n8n_cli(n, '--version').stdout.strip()
    m = re.search(r'(\d+)\.(\d+)\.(\d+)', out)
    if not m:
        aviso(f'não deu para ler a versão do n8n ("{out}")'); return
    v = tuple(int(x) for x in m.groups())
    if v[:2] < VERSAO_MINIMA:
        parar(f'o seu n8n é a versão {".".join(map(str, v))}. Os agentes precisam da {VERSAO_MINIMA[0]}.{VERSAO_MINIMA[1]} ou mais nova '
              '(por causa das tabelas de dados). Atualize o n8n e rode de novo.')
    ok(f'versão {".".join(map(str, v))}')


def copiar_para_n8n(n, local, nome):
    if n.get('local'):
        return local
    docker('exec', n['container'], 'mkdir', '-p', '/tmp/escritorio')
    docker('cp', local, f'{n["container"]}:/tmp/escritorio/{nome}')
    docker('exec', '-u', 'root', n['container'], 'chown', '-R', 'node', '/tmp/escritorio', check=False)
    return f'/tmp/escritorio/{nome}'


def credenciais_do_n8n(n, pasta):
    saida = os.path.join(pasta, 'creds.json') if n.get('local') else '/tmp/escritorio-creds.json'
    r = n8n_cli(n, 'export:credentials', '--all', f'--output={saida}', check=False)
    creds = []
    if r.returncode == 0:
        try:
            texto = open(saida, encoding='utf-8').read() if n.get('local') else docker('exec', n['container'], 'cat', saida).stdout
            creds = json.loads(texto or '[]')
        except Exception:
            creds = []
        apagar_no_n8n(n, saida)
    return creds


def criar_credencial(n, pasta, cred):
    arq = os.path.join(pasta, 'cred.json')
    json.dump([cred], open(arq, 'w', encoding='utf-8'))
    dentro = copiar_para_n8n(n, arq, 'cred.json')
    n8n_cli(n, 'import:credentials', f'--input={dentro}')
    apagar_no_n8n(n, dentro)
    if os.path.exists(arq): os.remove(arq)
    ok(f'credencial "{cred["name"]}" criada no n8n')
    return {'id': cred['id'], 'name': cred['name']}


# ---------------------------------------------------------------- cérebro dos agentes: Ollama (nuvem e deste PC) ou Gemini
OLLAMA = 'http://127.0.0.1:11434'
# modelos da nuvem do Ollama (rápidos e fortes; precisam da conta do Ollama), do preferido para o reserva
OLLAMA_NUVEM = ['gpt-oss:120b-cloud', 'deepseek-v3.1:671b-cloud', 'qwen3-coder:480b-cloud', 'kimi-k2:1t-cloud', 'glm-4.6:cloud', 'gpt-oss:20b-cloud']
# modelos deste PC que sabem usar ferramentas e escrevem bem em português (só como reserva: no processador são lentos)
OLLAMA_PREFERIDOS = ['qwen3:14b', 'qwen2.5:14b', 'qwen3:8b', 'qwen2.5:7b', 'llama3.1:8b', 'mistral-nemo']
# modelos pequenos demais para usar as telas e as ferramentas (respondem coisas sem sentido): ficam de fora
PEQUENOS = re.compile(r':(0\.5|1|1\.5|2|3|3\.8|4)b\b|llama3\.2(:latest)?$|tinyllama|gemma3?:(1|2|4)b|phi')
OLLAMA_MINIMO = (0, 12, 0)  # a primeira versão com os modelos da nuvem
OLLAMA_INSTALADOR = 'https://ollama.com/download/OllamaSetup.exe'
MAX_CEREBROS = 6


def ollama_exe():
    return shutil.which('ollama') or next((x for x in [os.path.join(LAD, r'Programs\Ollama\ollama.exe')] if LAD and os.path.exists(x)), None)


def ollama_modelos():
    try:
        return [m['name'] for m in json.loads(http(f'{OLLAMA}/api/tags', timeout=4)[1]).get('models', [])]
    except Exception:
        return None


def ligar_ollama():
    if ollama_modelos() is not None: return True
    exe = ollama_exe()
    if not exe: return False
    print('   ligando o Ollama numa janela nova (deixe ela aberta)...', flush=True)
    if os.name == 'nt':
        subprocess.Popen(f'start "Ollama (deixe aberta)" "{exe}" serve', shell=True)
    else:
        subprocess.Popen([exe, 'serve'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(1)
        if ollama_modelos() is not None: return True
    return False


def ollama_post(caminho, dados, timeout=15):
    req = urllib.request.Request(f'{OLLAMA}{caminho}', data=json.dumps(dados).encode(), headers={'content-type': 'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or '{}')


def usa_ferramentas(modelo):
    try:
        caps = ollama_post('/api/show', {'model': modelo}, timeout=8).get('capabilities')
        return True if caps is None else 'tools' in caps  # Ollama antigo não conta: tenta mesmo assim
    except Exception:
        return False


def ollama_versao():
    try:
        v = json.loads(http(f'{OLLAMA}/api/version', timeout=4)[1]).get('version', '0')
        return tuple(int(x) for x in re.findall(r'\d+', v)[:3])
    except Exception:
        return (0,)


def atualizar_ollama():
    """Ollama antigo não tem os modelos da nuvem: baixa o instalador oficial e atualiza sem perguntar nada."""
    if os.name != 'nt': return False
    print('   o Ollama deste PC é antigo: baixando e instalando a versão nova (uns 2 minutos)...', flush=True)
    destino = os.path.join(tempfile.gettempdir(), 'OllamaSetup.exe')
    try:
        urllib.request.urlretrieve(OLLAMA_INSTALADOR, destino)
    except Exception as e:
        aviso(f'não deu para baixar o Ollama novo ({e}). Baixe em ollama.com/download.'); return False
    for im in ('ollama app.exe', 'ollama.exe'):
        subprocess.run(['taskkill', '/IM', im, '/F'], capture_output=True)
    subprocess.run([destino, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-'])
    time.sleep(5)
    return ligar_ollama()


def testar_modelo(modelo, timeout=90):
    """Pergunta algo bobo ao modelo. Devolve 'ok', 'login' (a nuvem pede a conta do Ollama, com o link) ou o erro."""
    req = urllib.request.Request(f'{OLLAMA}/api/chat', headers={'content-type': 'application/json'}, data=json.dumps({
        'model': modelo, 'stream': False, 'keep_alive': '30m', 'options': {'num_predict': 8},
        'messages': [{'role': 'user', 'content': 'Responda só: ok'}]}).encode())
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as r:
            d = json.loads(r.read().decode() or '{}')
            return 'ok' if d.get('message') is not None else str(d.get('error') or 'sem resposta')
    except urllib.error.HTTPError as e:
        corpo = e.read().decode('utf-8', 'replace')
        try: d = json.loads(corpo)
        except Exception: d = {'error': corpo}
        if e.code in (401, 403) or re.search(r'unauthori|sign ?in', corpo, re.I):
            return ('login', d.get('signin_url') or '')
        return f'{e.code}: {d.get("error") or corpo}'[:200]
    except Exception as e:
        return str(e)[:200]


def entrar_no_ollama(link, modelo, espera=300):
    """Abre o login do Ollama (é de graça) e espera a nuvem liberar."""
    print('\n   >>> Os modelos da nuvem do Ollama pedem a sua conta do Ollama (é de graça).', flush=True)
    print('   >>> Vai abrir a página de login: entre (ou crie a conta) e clique em "Connect". Eu espero.', flush=True)
    import webbrowser
    if link:
        print(f'   (se a página não abrir, copie este endereço no navegador: {link})', flush=True)
        webbrowser.open(link)
    elif ollama_exe():
        if os.name == 'nt': subprocess.Popen(f'start "Entrar no Ollama" "{ollama_exe()}" signin', shell=True)
        else: subprocess.Popen([ollama_exe(), 'signin'])
    fim = time.time() + espera
    while time.time() < fim:
        time.sleep(8)
        if testar_modelo(modelo) == 'ok':
            ok('conta do Ollama conectada: modelos da nuvem liberados'); return True
    aviso('o login do Ollama não terminou. Os agentes usam os modelos deste PC até lá; '
          'quando entrar na conta, rode o instalar.bat de novo (ou só abra o escritório).')
    return False


def baixar_nuvem(modelos):
    """Registra os modelos da nuvem do Ollama (é rápido: não baixa o modelo, só o atalho)."""
    faltam = [m for m in OLLAMA_NUVEM if m not in modelos]
    if faltam: print('   registrando os modelos da nuvem do Ollama...', flush=True)
    for m in faltam:
        try: ollama_post('/api/pull', {'model': m, 'stream': False}, timeout=120)
        except Exception: pass
    return ollama_modelos() or modelos


def escolher_cerebros(modelos):
    """Testa os modelos e monta a lista: os da nuvem que responderam primeiro, depois os deste PC (reserva)."""
    pedido = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--modelo=')), None)
    nuvem = [m for m in OLLAMA_NUVEM if m in modelos] + [m for m in modelos if 'cloud' in m and m not in OLLAMA_NUVEM]
    locais = [m for p in OLLAMA_PREFERIDOS for m in modelos if (m == p or m == p + ':latest') and m not in nuvem]
    locais += [m for m in modelos if 'cloud' not in m and 'embed' not in m and m not in locais
               and not PEQUENOS.search(m) and usa_ferramentas(m)]
    funcionam, login = [], None
    for m in ([pedido] if pedido else []) + nuvem:
        r = testar_modelo(m)
        if r == 'ok':
            funcionam.append(m); print(f'   ok: {m} respondeu', flush=True)
        elif isinstance(r, tuple):
            login = login or (m, r[1])
            break  # sem a conta, nenhum da nuvem vai responder
        else:
            print(f'   {m} não respondeu agora ({r}): fica de reserva', flush=True)
    if not funcionam and login and entrar_no_ollama(login[1], login[0]):
        funcionam = [m for m in nuvem if testar_modelo(m) == 'ok']
    reservas = [m for m in nuvem if m not in funcionam] if funcionam else []
    nuvem_lista = list(dict.fromkeys(funcionam + reservas[:2]))[:MAX_CEREBROS - (1 if locais else 0)]
    lista = list(dict.fromkeys(nuvem_lista + locais))[:MAX_CEREBROS]  # sempre sobra lugar para um do PC, se a internet cair
    if not lista:  # só sobraram modelos pequenos: melhor que nada
        lista = [m for m in modelos if 'cloud' not in m and 'embed' not in m][:2]
    return lista, bool(funcionam)


def abrir_ollama_para_docker():
    """O n8n no Docker só alcança o Ollama se ele aceitar conexões de fora do Windows: ajusta e religa o Ollama."""
    if os.name != 'nt' or os.environ.get('OLLAMA_HOST', '').startswith('0.0.0.0'): return
    print('   deixando o Ollama acessível para o n8n do Docker (OLLAMA_HOST=0.0.0.0)...', flush=True)
    subprocess.run(['setx', 'OLLAMA_HOST', '0.0.0.0'], capture_output=True)
    os.environ['OLLAMA_HOST'] = '0.0.0.0'
    for im in ('ollama app.exe', 'ollama.exe'):
        subprocess.run(['taskkill', '/IM', im, '/F'], capture_output=True)
    time.sleep(2)
    ligar_ollama()


def cerebro(n, pasta):
    passo('Cérebro dos agentes (IA)')
    creds = credenciais_do_n8n(n, pasta)
    if '--gemini' not in sys.argv and ligar_ollama():
        if ollama_versao() < OLLAMA_MINIMO:
            atualizar_ollama()
        modelos = baixar_nuvem(ollama_modelos() or [])
        cerebros, nuvem_ok = escolher_cerebros(modelos)
        if not nuvem_ok and not any(not PEQUENOS.search(m) and 'cloud' not in m for m in cerebros):
            print('   sem a nuvem do Ollama: baixando o qwen2.5:7b (4,7 GB) para rodar neste PC como reserva...', flush=True)
            subprocess.run([ollama_exe() or 'ollama', 'pull', 'qwen2.5:7b'])
            cerebros, nuvem_ok = escolher_cerebros(ollama_modelos() or [])
        if cerebros:
            lembrar(cerebro='ollama', cerebros=cerebros)
            if not n.get('local'):
                abrir_ollama_para_docker()
            # credencial do escritório sempre com o endereço certo (127.0.0.1: no Windows, "localhost" às vezes não acha o Ollama)
            url = OLLAMA if n.get('local') else 'http://host.docker.internal:11434'
            try:
                cred = criar_credencial(n, pasta, {'id': 'escOllama0000001', 'name': 'Ollama (escritório)', 'type': 'ollamaApi',
                                                   'data': {'baseUrl': url, 'apiKey': ''}})
            except RuntimeError as e:
                cred = next(({'id': c['id'], 'name': c['name']} for c in creds if c.get('type') == 'ollamaApi'), None)
                if not cred: raise
                aviso(f'não deu para atualizar a credencial do Ollama ({str(e)[-120:]}): usando "{cred["name"]}"')
            ok('cérebros, do preferido para o reserva (se um falhar ou acabar, o agente troca sozinho): ' + ', '.join(cerebros))
            if not nuvem_ok:
                aviso('os modelos da nuvem do Ollama ainda não responderam: os agentes vão usar os deste PC, que são lentos sem placa de vídeo.')
            return {'tipo': 'ollama', 'cerebros': cerebros, 'cred': cred}
    gem = next(({'id': c['id'], 'name': c['name']} for c in creds if c.get('type') == 'googlePalmApi'), None)
    if not gem:
        parar('os agentes precisam de uma IA: instale o Ollama (ollama.com/download) e rode de novo.')
    aviso('sem o Ollama: usando o Gemini (credencial que já está no n8n).')
    lembrar(cerebro='gemini')
    return {'tipo': 'gemini', 'cred': gem}


# ---------------------------------------------------------------- WhatsApp (Evolution no Docker, por QR code)
EVO_PASTA = os.path.join(RAIZ, 'servidor', 'evolution')
EVO_PORTA = 8080


def evo_api(caminho, key, metodo='GET', dados=None, timeout=15):
    req = urllib.request.Request(f'http://localhost:{EVO_PORTA}{caminho}', method=metodo, headers={'apikey': key, 'content-type': 'application/json'},
                                 data=json.dumps(dados).encode() if dados is not None else None)
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or '{}')


def evo_chave():
    """A chave da Evolution desta máquina, guardada no .env que o docker compose usa (criado na primeira vez)."""
    env = os.path.join(EVO_PASTA, '.env')
    if os.path.exists(env):
        m = re.search(r'^AUTHENTICATION_API_KEY=(.+)$', open(env, encoding='utf-8').read(), re.M)
        if m: return m.group(1).strip()
    import secrets
    chave = secrets.token_hex(20)
    with open(env, 'w', encoding='utf-8') as f:
        f.write(f"""SERVER_URL=http://localhost:{EVO_PORTA}
AUTHENTICATION_API_KEY={chave}
LANGUAGE=pt-BR
DEL_INSTANCE=false
DATABASE_PROVIDER=postgresql
DATABASE_CONNECTION_URI=postgresql://evolution:evolution@postgres:5432/evolution?schema=public
DATABASE_CONNECTION_CLIENT_NAME=escritorio
DATABASE_SAVE_DATA_INSTANCE=true
DATABASE_SAVE_DATA_NEW_MESSAGE=true
DATABASE_SAVE_MESSAGE_UPDATE=true
DATABASE_SAVE_DATA_CONTACTS=true
DATABASE_SAVE_DATA_CHATS=true
DATABASE_SAVE_DATA_LABELS=true
DATABASE_SAVE_DATA_HISTORIC=true
CACHE_REDIS_ENABLED=false
CACHE_LOCAL_ENABLED=true
CONFIG_SESSION_PHONE_CLIENT=Escritorio 3D
CONFIG_SESSION_PHONE_NAME=Chrome
QRCODE_LIMIT=30
""")
    return chave


def evo_no_ar(key):
    try: evo_api('/instance/fetchInstances', key, timeout=5); return True
    except Exception: return False


def subir_evolution():
    """Sobe a Evolution do escritório no Docker (primeira vez baixa as imagens: alguns minutos)."""
    key = evo_chave()
    if evo_no_ar(key): return key
    print('   ligando a Evolution no Docker (na primeira vez baixa as imagens, pode levar alguns minutos)...', flush=True)
    r = docker('compose', '-f', os.path.join(EVO_PASTA, 'docker-compose.yml'), 'up', '-d', check=False)
    if r.returncode != 0:
        aviso('a Evolution não subiu: ' + (r.stderr or r.stdout).strip()[-300:]); return None
    for _ in range(90):
        if evo_no_ar(key): return key
        time.sleep(4)
    aviso('a Evolution não respondeu em http://localhost:8080 (veja o container escritorio_evolution no Docker Desktop).')
    return None


def estado_whatsapp(key, inst):
    try: return (evo_api(f'/instance/connectionState/{inst}', key).get('instance') or {}).get('state') or ''
    except Exception: return ''


def conectar_whatsapp(key, inst, espera=180):
    """Cria a instância (se precisar) e mostra o QR code numa página que se atualiza sozinha, até o celular conectar."""
    try:
        nomes = [i.get('name') or (i.get('instance') or {}).get('instanceName') for i in evo_api('/instance/fetchInstances', key)]
        if inst not in nomes:
            evo_api('/instance/create', key, 'POST', {'instanceName': inst, 'integration': 'WHATSAPP-BAILEYS', 'qrcode': True})
            try: evo_api(f'/settings/set/{inst}', key, 'POST', {'rejectCall': False, 'groupsIgnore': True, 'alwaysOnline': False,
                                                                   'readMessages': False, 'readStatus': False, 'syncFullHistory': True})
            except Exception: pass
    except Exception as e:
        aviso(f'não deu para criar a instância do WhatsApp: {e}'); return False
    if estado_whatsapp(key, inst) == 'open':
        ok('WhatsApp comercial já está conectado'); return True
    png, pagina = os.path.join(RAIZ, 'whatsapp-qrcode.png'), os.path.join(RAIZ, 'whatsapp-qrcode.html')
    with open(pagina, 'w', encoding='utf-8') as f:
        f.write('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="15"><title>Conectar o WhatsApp</title>'
                '<body style="font:18px sans-serif;text-align:center;background:#111;color:#eee"><h2>Conecte o WhatsApp comercial</h2>'
                '<p>No celular: WhatsApp → Aparelhos conectados → Conectar um aparelho → aponte para o código.</p>'
                f'<img src="whatsapp-qrcode.png?{int(time.time())}" style="width:360px;background:#fff;padding:12px"><p>O código se renova sozinho.</p>')
    print('   abrindo o QR code: no celular do comercial, WhatsApp → Aparelhos conectados → Conectar um aparelho.', flush=True)
    aberto, fim, ultimo = False, time.time() + espera, 0
    while time.time() < fim:
        if time.time() - ultimo > 25:  # o código vale ~30 s: busca outro
            ultimo = time.time()
            try:
                b64 = evo_api(f'/instance/connect/{inst}', key).get('base64') or ''
                if b64:
                    import base64
                    open(png, 'wb').write(base64.b64decode(b64.split(',', 1)[-1]))
                    if not aberto:
                        aberto = True
                        import webbrowser; webbrowser.open('file:///' + pagina.replace('\\', '/'))
            except Exception:
                pass
        if estado_whatsapp(key, inst) == 'open':
            ok('WhatsApp comercial conectado!')
            for arq in (png,):
                try: os.remove(arq)
                except Exception: pass
            return True
        time.sleep(3)
    aviso('o WhatsApp ainda não foi conectado. Na próxima vez que abrir o escritório, o QR code aparece de novo.')
    return False


def evolution(n):
    passo('WhatsApp (Evolution)')
    evo = escolher(n['lista'], 'evolution') if DOCKER else None
    if evo and evo['nome'] != 'escritorio_evolution':
        # já existe uma Evolution neste PC (de outro projeto): usa ela
        if evo['estado'] != 'running': ligar_grupo(evo)
        info = inspecionar(evo['nome']); env = env_de(info)
        key, interna = env.get('AUTHENTICATION_API_KEY', ''), int(env.get('SERVER_PORT', '8080') or 8080)
        externa = porta_no_pc(evo['nome'], interna)
        redes = set((n['info'].get('NetworkSettings', {}).get('Networks') or {}).keys()) & set((info.get('NetworkSettings', {}).get('Networks') or {}).keys())
        url = f'http://localhost:{externa}' if n.get('local') and externa else f'http://{evo["nome"]}:{interna}' if redes else f'http://host.docker.internal:{externa or interna}'
        ok(f'usando a Evolution que já existe ({evo["nome"]}) em {url}')
        return {'url': url, 'key': key, 'instancia': INSTANCIA_PADRAO}
    if not DOCKER:
        aviso('sem o Docker não dá para instalar a Evolution: a Ana lê o WhatsApp pelo WhatsApp Web aberto numa tela do escritório.')
        return {'url': '', 'key': '', 'instancia': INSTANCIA_PADRAO}
    key = subir_evolution()
    if not key:
        return {'url': '', 'key': '', 'instancia': INSTANCIA_PADRAO}
    lembrar(evolution=True)
    conectar_whatsapp(key, INSTANCIA_PADRAO)
    url = f'http://localhost:{EVO_PORTA}' if n.get('local') else f'http://host.docker.internal:{EVO_PORTA}'
    ok(f'Evolution do escritório em {url}, instância "{INSTANCIA_PADRAO}"')
    return {'url': url, 'key': key, 'instancia': INSTANCIA_PADRAO}


LOCAL = os.path.join(RAIZ, 'escritorio-local.json')  # o que este PC lembra entre uma instalação e outra (fica fora do git)


def lembrar(**kw):
    dados = {}
    try: dados = json.load(open(LOCAL, encoding='utf-8'))
    except Exception: pass
    dados.update(kw)
    json.dump(dados, open(LOCAL, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    return dados


def lembrado(chave):
    try: return json.load(open(LOCAL, encoding='utf-8')).get(chave)
    except Exception: return None


def editor_ligado():
    try:
        http(f'http://localhost:{ABEKYO_PORTA}/', timeout=4); return True
    except Exception:
        return False


def e_abekyo(pasta):
    try: return json.load(open(os.path.join(pasta, 'package.json'), encoding='utf-8')).get('name') == 'abekyo-editor'
    except Exception: return False


def achar_abekyo():
    """Procura a pasta do abekyo-editor nos lugares de costume (até 3 níveis), sem varrer o disco inteiro."""
    junto = os.path.join(RAIZ, 'abekyo-editor')  # o editor vem dentro da pasta do escritório
    if e_abekyo(junto): return junto
    salvo = lembrado('abekyo')
    if salvo and e_abekyo(salvo): return salvo
    casa = os.path.expanduser('~')
    raizes = [os.path.dirname(RAIZ), casa] + [os.path.join(casa, x) for x in ('Downloads', 'Documents', 'Documentos', 'Desktop', 'Área de Trabalho', 'OneDrive')]
    if os.name == 'nt':
        raizes += [f'{l}:\\' for l in 'CDEFGH' if os.path.exists(f'{l}:\\')]
    vistos = set()
    for raiz in raizes:
        for base, dirs, _ in os.walk(raiz):
            if base in vistos: dirs[:] = []; continue
            vistos.add(base)
            if base[len(raiz):].count(os.sep) >= 3: dirs[:] = []
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'Windows', 'Program Files', 'Program Files (x86)', 'AppData', '$Recycle.Bin')]
            if 'abekyo' in os.path.basename(base).lower() and e_abekyo(base):
                return base
    return None


def ligar_abekyo():
    """Liga o editor de vídeo da Carla numa janela própria (npm install na primeira vez). Devolve True se ficou no ar."""
    if editor_ligado(): return True
    pasta = achar_abekyo()
    if not pasta:
        return False
    lembrar(abekyo=pasta)
    npm = shutil.which('npm')
    if not npm:
        aviso('o comando npm não está instalado (vem junto com o Node.js): sem ele não dá para ligar o editor.'); return False
    if not os.path.isdir(os.path.join(pasta, 'node_modules')):
        print('   primeira vez: instalando o editor (npm install, pode levar alguns minutos)...', flush=True)
        if subprocess.run([npm, 'install', '--no-audit', '--no-fund'], cwd=pasta).returncode != 0:
            aviso('o npm install do editor não terminou (veja as mensagens acima).'); return False
    print(f'   ligando o editor numa janela nova (deixe ela aberta): {pasta}', flush=True)
    if os.name == 'nt':
        subprocess.Popen(f'start "Editor da Carla (deixe aberta)" /d "{pasta}" cmd /k npm run dev', shell=True)
    else:
        subprocess.Popen([npm, 'run', 'dev'], cwd=pasta, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(90):  # a primeira compilação do Next.js demora
        time.sleep(2)
        if editor_ligado(): return True
    return False


def abekyo(n):
    passo('Editor de vídeo da Carla (Abekyo)')
    if ligar_abekyo():
        ok(f'editor ligado em http://localhost:{ABEKYO_PORTA}')
    else:
        aviso(f'o editor não ligou em http://localhost:{ABEKYO_PORTA} (precisa do Node.js). A Carla escreve roteiros e carrosséis do mesmo jeito.')
    # o n8n no Docker enxerga o PC por host.docker.internal
    return f'http://localhost:{ABEKYO_PORTA}' if n.get('local') else f'http://host.docker.internal:{ABEKYO_PORTA}'


def js_str(v):
    return "'" + str(v).replace('\\', '\\\\').replace("'", "\\'") + "'"


def preparar_fluxos(n, cred, evo, abekyo_n8n, pasta):
    arquivos = []
    for arq, wid in FLUXOS:
        d = json.load(open(os.path.join(RAIZ, 'n8n', arq), encoding='utf-8'))
        d['id'] = wid
        for no in d['nodes']:
            if no['type'].endswith(('lmChatOllama', 'lmChatGoogleGemini')):  # o cérebro de cada agente
                if cred['tipo'] == 'ollama':
                    opcoes = no['parameters'].get('options') or {'temperature': 0.4, 'numCtx': 16384, 'keepAlive': '30m'}
                    no.update(type='@n8n/n8n-nodes-langchain.lmChatOllama', typeVersion=1,
                              parameters={'model': '={{ $json.modelo }}', 'options': opcoes}, credentials={'ollamaApi': cred['cred']})
                else:
                    no.update(type='@n8n/n8n-nodes-langchain.lmChatGoogleGemini', typeVersion=1,
                              parameters={'modelName': 'models/gemini-2.5-flash', 'options': {'temperature': 0.4}}, credentials={'googlePalmApi': cred['cred']})
            url = no['parameters'].get('url')
            if isinstance(url, str):  # chamadas internas ao n8n (ferramentas, vigia do Fábio) e ao editor de vídeo
                url = url.replace('http://localhost:5678', f"http://localhost:{n['interna']}")
                no['parameters']['url'] = url.replace('http://localhost:3000', abekyo_n8n)
            if no['name'] in ('Escolher cérebro', 'Trocar cérebro'):  # a lista de cérebros deste PC
                lista = cred['cerebros'] if cred['tipo'] == 'ollama' else ['gemini']
                no['parameters']['jsCode'] = re.sub(r'const CEREBROS = \[[^\]]*\];', 'const CEREBROS = ' + json.dumps(lista) + ';', no['parameters']['jsCode'])
            if no['type'] == 'n8n-nodes-base.code' and ('const EVOLUTION_URL' in no['parameters'].get('jsCode', '') or no['name'] == 'Preparar'):
                c = no['parameters']['jsCode']
                c = re.sub(r"const N8N = '[^']*';", f"const N8N = 'http://localhost:{n['interna']}';", c)
                c = re.sub(r"const CODIGO_ENVIO = '[^']*';", f'const CODIGO_ENVIO = {js_str(codigo_envio())};', c)
                c = re.sub(r"const EVOLUTION_URL = '[^']*';", f'const EVOLUTION_URL = {js_str(evo["url"])};', c)
                c = re.sub(r"const EVOLUTION_KEY = '[^']*';", f'const EVOLUTION_KEY = {js_str(evo["key"])};', c)
                c = re.sub(r"const INSTANCIA = '[^']*';", f'const INSTANCIA = {js_str(evo["instancia"])};', c)
                no['parameters']['jsCode'] = c
        destino = os.path.join(pasta, arq)
        json.dump(d, open(destino, 'w', encoding='utf-8'), ensure_ascii=False)
        arquivos.append((destino, arq, wid, d['name']))
    return arquivos


def importar(n, arquivos):
    passo('Fluxos dos agentes')
    for local, arq, wid, nome in arquivos:
        dentro = copiar_para_n8n(n, local, arq)
        n8n_cli(n, 'import:workflow', f'--input={dentro}')
        # n8n 2.x publica; o 1.x ativa
        r = n8n_cli(n, 'publish:workflow', f'--id={wid}', check=False)
        if r.returncode != 0:
            n8n_cli(n, 'update:workflow', f'--id={wid}', '--active=true')
        ok(f'{nome} importado e ativo')
    if n.get('local'):
        if not reiniciar_n8n_local(n):
            parar('o n8n não voltou depois de reiniciar. Ligue o n8n de novo e rode o instalar.bat.')
        return
    apagar_no_n8n(n, '/tmp/escritorio')
    print('   reiniciando o n8n para ligar os fluxos...', flush=True)
    docker('restart', n['container'])
    if not esperar_n8n(n['porta']):
        parar('o n8n não voltou depois de reiniciar. Veja o container no Docker Desktop.')


def testar(n):
    passo('Teste')
    for _ in range(15):
        try:
            _, corpo = http(f'http://localhost:{n["porta"]}/webhook/escritorio/estado', timeout=15)
            est = json.loads(corpo)
            ok(f'o escritório já conversa com o n8n: agentes de verdade = {", ".join(est.get("ativos", []))}')
            return True
        except Exception as e:
            erro = e
            time.sleep(2)
    aviso(f'o Central não respondeu ({erro}). Abra o n8n e confira se os 4 fluxos "Escritório · ..." estão ativos.')
    return False


def codigo_envio():
    """Código secreto desta instalação: só o escritório (servido neste PC) pode pedir para enviar no WhatsApp."""
    c = lembrado('codigo_envio')
    if not c:
        import secrets
        c = secrets.token_hex(16); lembrar(codigo_envio=c)
    return c


def gravar_config(n):
    env = os.path.join(EVO_PASTA, '.env')
    chave = (re.search(r'^AUTHENTICATION_API_KEY=(.+)$', open(env, encoding='utf-8').read(), re.M) if os.path.exists(env) else None)
    evo = {'url': f'http://localhost:{EVO_PORTA}', 'chave': chave.group(1).strip()} if chave else None
    with open(os.path.join(RAIZ, 'escritorio-config.js'), 'w', encoding='utf-8') as f:
        f.write(f"// gerado pelo instalar.bat: endereços do n8n, do editor de vídeo e da Evolution deste PC (não compartilhe)\n"
                f"window.ESCRITORIO_N8N = 'http://localhost:{n['porta']}';\nwindow.ESCRITORIO_ABEKYO = 'http://localhost:{ABEKYO_PORTA}';\n"
                f"window.ESCRITORIO_EVOLUTION = {json.dumps(evo)};\nwindow.ESCRITORIO_PASTA = {json.dumps(RAIZ)};\n"
                f"window.ESCRITORIO_ENVIO = {json.dumps(codigo_envio())};\n")
    if evo:
        with open(os.path.join(RAIZ, 'whatsapp-evolution.txt'), 'w', encoding='utf-8') as f:
            f.write(f"Painel da Evolution (WhatsApp comercial): {evo['url']}/manager\nServer URL: {evo['url']}\nAPI Key: {evo['chave']}\n"
                    f"Instância: {INSTANCIA_PADRAO}\n(não compartilhe a chave)\n")


def versao_da_pasta():
    try: return open(os.path.join(RAIZ, 'n8n', 'versao.txt'), encoding='utf-8').read().strip()
    except Exception: return ''


def versao_no_n8n(n):
    try: return json.loads(http(f'http://localhost:{n["porta"]}/webhook/escritorio/estado', timeout=15)[1]).get('versao')
    except Exception: return None


def instalar_tudo(n):
    conferir_versao(n)
    with tempfile.TemporaryDirectory() as pasta:
        cred = cerebro(n, pasta)
        evo = evolution(n)
        abekyo_n8n = abekyo(n)
        importar(n, preparar_fluxos(n, cred, evo, abekyo_n8n, pasta))
    testar(n)
    gravar_config(n)
    lembrar(versao=versao_da_pasta(), atualizado_em=time.time())


# ---------------------------------------------------------------- atualizar sozinho pelo zip baixado
# Basta baixar o zip novo (escritorio-3d-agentes*.zip) na pasta Downloads: o abrir-escritorio.bat (ou o instalar.bat)
# acha o zip, copia os arquivos novos por cima desta pasta (mantendo as configurações deste PC) e reinstala os agentes.
NAO_SOBRESCREVER = {'escritorio-local.json', 'escritorio-config.js', 'servidor/evolution/.env', 'whatsapp-evolution.txt'}


def zip_mais_novo():
    import glob
    casa = os.path.expanduser('~')
    pastas = [os.path.join(casa, 'Downloads'), os.path.join(casa, 'OneDrive', 'Downloads'), os.path.join(casa, 'Desktop'),
              os.path.join(casa, 'Área de Trabalho'), os.path.dirname(RAIZ)]
    zips = [z for d in pastas for z in glob.glob(os.path.join(d, 'escritorio-3d-agentes*.zip'))]
    return max(zips, key=os.path.getmtime) if zips else None


def atualizar_pelo_zip():
    import zipfile
    z = zip_mais_novo()
    if not z: return False
    marca = f'{os.path.basename(z)}|{int(os.path.getmtime(z))}'
    if lembrado('zip_aplicado') == marca: return False
    # zip baixado antes da última atualização desta pasta (um zip velho esquecido em Downloads): não volta versão
    base = lembrado('atualizado_em') or (os.path.getctime(os.path.join(RAIZ, 'n8n', 'versao.txt')) if os.path.exists(os.path.join(RAIZ, 'n8n', 'versao.txt')) else 0)
    if os.path.getmtime(z) <= base: return False
    try:
        with zipfile.ZipFile(z) as zf:
            nomes = zf.namelist()
            vtxt = next((n for n in nomes if n.endswith('n8n/versao.txt')), None)
            if not vtxt: return False
            prefixo = vtxt[:-len('n8n/versao.txt')]
            nova = zf.read(vtxt).decode('utf-8', 'replace').strip()
            if nova == versao_da_pasta():
                lembrar(zip_aplicado=marca); return False
            passo(f'Atualizando o escritório para a versão {nova} (do arquivo {os.path.basename(z)})')
            ext_antes = versao_da_extensao()
            for n in nomes:
                rel = n[len(prefixo):] if n.startswith(prefixo) else n
                if not rel or rel.endswith('/') or rel in NAO_SOBRESCREVER or '..' in rel.split('/'): continue
                destino = os.path.join(RAIZ, *rel.split('/'))
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                try:
                    with zf.open(n) as src, open(destino, 'wb') as dst: shutil.copyfileobj(src, dst)
                except OSError as e:
                    aviso(f'não deu para trocar {rel} ({e})')
    except zipfile.BadZipFile:
        aviso(f'o arquivo {os.path.basename(z)} está incompleto (o download terminou?)'); return False
    lembrar(zip_aplicado=marca, atualizado_em=time.time())
    ok(f'pasta atualizada para a versão {nova}')
    if versao_da_extensao() != ext_antes:
        lembrar(extensao_nova=versao_da_extensao())
    return True


def versao_da_extensao():
    try: return json.load(open(os.path.join(RAIZ, 'extensao', 'manifest.json'), encoding='utf-8')).get('version', '')
    except Exception: return ''


def avisar_extensao_nova():
    """A extensão veio nova na atualização: o Chrome só usa depois de recarregar (um clique em chrome://extensions)."""
    v = lembrado('extensao_nova')
    if not v: return
    lembrar(extensao_nova='')
    passo(f'Extensão do Chrome nova ({v})')
    print('   >>> Na página de extensões que vai abrir, clique em ⟳ (recarregar) na extensão "Escritório dos Agentes · telas".', flush=True)
    print('   >>> Depois, recarregue a página do escritório (F5).', flush=True)
    if os.name == 'nt':
        subprocess.Popen('start "" chrome "chrome://extensions"', shell=True)


def main():
    if '--sem-atualizar' not in sys.argv and atualizar_pelo_zip():
        # roda de novo com o instalador novo que acabou de chegar
        sys.exit(subprocess.run([sys.executable, os.path.abspath(__file__), *sys.argv[1:], '--sem-atualizar']).returncode)
    if '--ligar' in sys.argv:
        n = None
        try:
            n = ligar_n8n(); gravar_config(n)
        except SystemExit:
            pass  # sem n8n o escritório abre do mesmo jeito, com a equipe simulada
        # pasta atualizada e n8n com os fluxos de antes: instala a versão nova sozinho antes de abrir
        if n and versao_da_pasta() and versao_no_n8n(n) != versao_da_pasta():
            print(f'\nOs agentes no n8n estão desatualizados: atualizando para a versão {versao_da_pasta()}...', flush=True)
            try:
                instalar_tudo(n)
            except (RuntimeError, SystemExit) as e:
                aviso(f'a atualização não terminou ({e}). Rode o instalar.bat para ver o que faltou.')
        if lembrado('cerebro') == 'ollama':
            if ollama_modelos() is None:
                passo('Ollama (cérebro dos agentes)')
                ok('Ollama ligado') if ligar_ollama() else aviso('o Ollama não ligou: abra o Ollama pelo menu Iniciar')
            # a conta do Ollama saiu? abre o login de novo antes de abrir o escritório
            nuvem = [m for m in (lembrado('cerebros') or []) if 'cloud' in m]
            r = testar_modelo(nuvem[0], timeout=30) if nuvem and ollama_modelos() is not None else 'ok'
            if isinstance(r, tuple):
                passo('Conta do Ollama')
                entrar_no_ollama(r[1], nuvem[0], espera=150)
        if lembrado('evolution') and DOCKER:
            key = subir_evolution()
            if key and estado_whatsapp(key, INSTANCIA_PADRAO) != 'open':
                passo('WhatsApp comercial desconectado')
                conectar_whatsapp(key, INSTANCIA_PADRAO, espera=120)
        if achar_abekyo() and not editor_ligado():
            passo('Editor de vídeo da Carla')
            ok('editor ligado') if ligar_abekyo() else aviso('o editor de vídeo não ligou')
        avisar_extensao_nova()
        return
    print(f'Instalação dos agentes do Escritório 3D (versão {versao_da_pasta()})')
    try:
        instalar_tudo(ligar_n8n())
    except RuntimeError as e:
        parar(str(e))
    avisar_extensao_nova()
    print('\nPronto! Agora é só abrir o escritório pelo abrir-escritorio.bat.')
    print('Primeira vez neste Chrome? Instale a extensão da pasta "extensao" em chrome://extensions')
    print('(ative o Modo do desenvolvedor, clique em "Carregar sem compactação" e escolha a pasta).')
    if os.name == 'nt' and '--sem-abrir' not in sys.argv:
        print('\nAbrindo o escritório...')
        subprocess.Popen(f'start "Escritório 3D" cmd /c "{os.path.join(RAIZ, "abrir-escritorio.bat")}"', shell=True)


if __name__ == '__main__':
    main()
