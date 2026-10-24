# Escritório dos Agentes

Escritório 3D no navegador para acompanhar uma equipe de agentes de IA. Os agentes trabalham, fazem reunião e pausa. O quadro grande da parede é o kanban das tarefas deles, e a parede da esquerda tem um mural de avisos.

Tudo fica em um único arquivo: [`escritorio-3d.html`](escritorio-3d.html). Ele usa Three.js r128, carregado por CDN.

## Como instalar e abrir

Precisa ter no PC: **Python**, **Chrome**, **Node.js**, o **n8n** (no Docker Desktop ou instalado direto; versão 1.113 ou mais nova, ou qualquer 2.x), o **[Ollama](https://ollama.com/download)** (o cérebro dos agentes) e o **Docker Desktop** (para o WhatsApp pela Evolution).

1. **Uma vez:** dois cliques em **`instalar.bat`**. Ele não faz perguntas: liga o Docker e o n8n, liga o Ollama e registra os modelos da nuvem do Ollama, sobe a Evolution no Docker e abre o QR code do WhatsApp, liga o editor de vídeo da Carla (que já vem na pasta `abekyo-editor`), importa e ativa os 4 fluxos, reinicia o n8n, testa e abre o escritório.
   - **Só duas coisas são suas:** apontar o celular do comercial para o QR code (WhatsApp → Aparelhos conectados → Conectar um aparelho) e, quando abrir a página de login do Ollama, entrar na sua conta do Ollama (é de graça) e clicar em **Connect**. O instalador espera você entrar, testa cada IA de verdade e só então continua.
2. **Uma vez neste Chrome:** instale a extensão (explicado abaixo).
3. **Sempre:** dois cliques em **`abrir-escritorio.bat`**. Ele liga o que estiver desligado (Docker, n8n, Ollama, Evolution e o editor da Carla), mostra o QR code de novo se o WhatsApp desconectar, atualiza os agentes sozinho quando a pasta tiver uma versão nova, sobe o servidor local e abre o escritório no Chrome em http://127.0.0.1:8765/escritorio-3d.html.

**Como atualizar (sem apagar nada):** baixe o zip novo (`escritorio-3d-agentes*.zip`) e deixe na pasta **Downloads**. Na próxima vez que abrir o `abrir-escritorio.bat`, ele acha o zip, copia os arquivos novos por cima desta pasta (as configurações deste PC ficam), reinstala os agentes e abre o escritório. Se a extensão do Chrome mudou, ele abre a página `chrome://extensions`: clique em **⟳** na extensão do escritório e aperte F5 no escritório. No canto de baixo, à direita, o escritório mostra a versão dele e a da extensão (⚠ quando algo está desatualizado); clicando ali, ele testa se os agentes conseguem usar cada tela.

**Instale uma vez a extensão** da pasta [`extensao`](extensao): abra `chrome://extensions`, ative o **Modo do desenvolvedor**, clique em **Carregar sem compactação** e escolha a pasta `extensao`. Com ela, cada monitor, a TV e a caixa de som viram navegadores de verdade (voltar, avançar, recarregar, início e barra de endereço), usando os logins que você já tem no Chrome. A extensão só tira o bloqueio de "abrir dentro de outro site" nas telas da aba do escritório.

**Atualizou a pasta? Recarregue a extensão:** o Chrome continua usando a versão antiga até você abrir `chrome://extensions` e clicar em **⟳** na extensão "Escritório dos Agentes · telas". O escritório avisa quando a extensão está desatualizada (sem isso os agentes não conseguem ler as telas).

| Tela | Abre em |
| --- | --- |
| PC 1 e PC 2 | claude.ai (relatórios diário e semanal) |
| PC 3 | planilha Leads tráfego |
| PC 4 e PC 5 | Google Agenda (lista e semana) |
| PC 6 | sistema do Cantinho do Au Au |
| TV | youtube.com completo, com busca, login e tudo |
| Caixa de som | open.spotify.com (player completo; o volume baixa com a distância) |

### Guias nos computadores

Com a extensão, cada PC é um Chrome com **guias**:

- **+** abre uma guia nova, **×** fecha (ou clique com o botão do meio na guia), e clicar numa guia troca para ela.
- Links que abririam uma guia nova (os de "abrir em nova guia", Ctrl+clique ou botão do meio) abrem uma guia no próprio PC. Com Ctrl ou botão do meio, a guia abre em segundo plano.
- Cada PC tem até 8 guias. No limite, o link abre na guia atual.
- As guias ficam salvas neste navegador e voltam quando o escritório abre de novo.
- Janelinhas abertas pelo próprio site (como o login do Google) continuam abrindo fora do escritório, porque o login depende delas.

Se você já tinha a extensão instalada, clique em **Recarregar** nela em `chrome://extensions` para pegar a versão 1.1.0.

Sem a extensão, o escritório funciona com as telas limitadas abaixo:

| Objeto | O que abre |
| --- | --- |
| PC 1 e PC 2 | painel das tarefas agendadas do Claude (relatório diário e semanal) |
| PC 3 | planilha "Leads trafego" do Google Sheets |
| PC 4 e PC 5 | Google Agenda (lista e semana) |
| PC 6 | sistema do Cantinho do Au Au (cole o endereço na primeira vez) |
| TV | YouTube (cole um link na barra de cima) |
| Caixa de som | Spotify (cole um link de playlist, álbum ou música) |

Clique num monitor, na TV ou no painel do Spotify para "sentar": a câmera vai até a tela e o mouse passa a usar o site. **Esc** ou **Levantar** volta a andar.

### TV com busca do YouTube

O site do YouTube não pode abrir dentro de outra página, então a TV usa o player oficial do YouTube (com todos os controles) e uma busca própria. Para buscar, crie uma chave grátis da **YouTube Data API v3** em console.cloud.google.com e cole na TV na primeira busca. Sem chave, cole o link de um vídeo ou playlist.

### Caixa de som com Spotify

A caixa de som vira um aparelho chamado **Escritório 3D** na sua conta do Spotify, com playlists, controles e volume que muda com a distância. Precisa de **Spotify Premium** e de um app grátis em developer.spotify.com/dashboard com o Redirect URI `http://127.0.0.1:8765/escritorio-3d.html` (marque Web Playback SDK e Web API). Cole o Client ID no painel e clique em Conectar. Sem Premium, o painel tem um player simples.

O som ambiente tem posição: o teclado de quem está trabalhando, o ar-condicionado e a máquina de café ficam mais altos de perto. A TV e a caixa de som do Spotify (conectada) também baixam o volume conforme você se afasta.

### Mesa de som

Cada tela é um navegador independente, então várias podem tocar ao mesmo tempo. O botão **Som** (em cima) mostra quantas estão tocando e abre a mesa de som:

- **Volume geral** e botão de mudo.
- **Como o som se mistura:** *Pela distância* (cada tela mais alta de perto), *Volume fixo* (todas iguais, de qualquer lugar) ou *Só a tela em uso* (sentado numa tela, as outras ficam mudas).
- **Um som por vez:** quando algo começa a tocar numa tela, as outras pausam.
- **Telas:** volume, mudo e pausar de cada PC, da TV e do Spotify, com o nome do que está tocando. A guia que toca som ganha um 🔊, como no Chrome.
- **Ambiente:** teclados, ar-condicionado e máquina de café.

As escolhas ficam salvas neste navegador. Para o **🔊**, o **Pausar** e o **Um som por vez**, recarregue a extensão em `chrome://extensions` (versão 1.3.0).

Pela página do Claude (link do artifact), outros sites não podem aparecer dentro do escritório. Lá os computadores abrem as janelas do próprio escritório, com agenda e chat do Claude.

## Controles

| Ação | Como |
| --- | --- |
| Visão de cima | arrastar para girar, rolar para zoom |
| Andar pelo escritório | botão **Andar pelo escritório** |
| Olhar em volta | mover o mouse (entra em tela cheia com o mouse preso, como no Minecraft) |
| Pausar | **Esc** abre o menu de pausa (voltar, trocar visão, sair) |
| Girar sem mouse | Q / E ou setas ← → |
| Andar / correr / pular | W A S D ou setas / Shift / Espaço |
| Trocar 1ª ↔ 3ª pessoa | tecla **V** ou botão |
| Ver um agente | mirar com a cruz no centro e clicar |
| Quadro de tarefas (kanban) | clicar no quadro grande da parede do fundo |
| Mural de avisos | clicar no quadro de cortiça da parede da esquerda |
| Mapa do Segundo Cérebro | botão **Mapa do Segundo Cérebro** |
| Mesa de som | botão **Som** |

## Agentes de verdade (n8n)

O **Fábio · Gestor**, a **Ana · Comercial** e a **Carla · Conteúdo e vídeos** são agentes de verdade: cada um é um fluxo no n8n do seu PC (um AI Agent com ferramentas e o Ollama deste PC como cérebro).

**Cérebro (Ollama, com troca automática):** os agentes usam os **modelos da nuvem do Ollama** (`gpt-oss:120b-cloud`, `deepseek-v3.1:671b-cloud`, `qwen3-coder:480b-cloud`, `kimi-k2:1t-cloud`...), que rodam nos servidores do Ollama: respondem em segundos mesmo num PC sem placa de vídeo. Os modelos baixados no PC (`qwen2.5:7b`, `llama3.2`...) ficam no fim da lista, como reserva. Cada agente tenta o primeiro da lista; se ele falhar ou acabar o limite de uso, o agente troca sozinho para o próximo (o que falhou fica de fora 30 minutos) e você nem percebe. Se todos falharem, o agente diz na conversa o motivo (por exemplo: falta entrar na conta do Ollama, ou o Ollama está desligado), e cada pedido tem no máximo 6 minutos para terminar (nada de carregar para sempre). O histórico de cada agente mostra qual cérebro respondeu ("terminou (cérebro: ...)"). O instalador testa cada modelo antes de usar, atualiza o Ollama sozinho se ele for antigo (os modelos da nuvem precisam da versão 0.12 ou mais nova) e deixa de fora os modelos pequenos demais (1b a 4b, como o llama3.2:3b), que não sabem usar as telas. Se a conta do Ollama sair, o `abrir-escritorio.bat` abre o login de novo. Para pôr um modelo na frente da lista: `python tools\instalar.py --modelo=nome`. Sem o Ollama, o instalador usa o Gemini que já estiver no n8n (ou force com `--gemini`). Os outros (Bruno, Davi e Eva) continuam simulados até ganharem o fluxo deles.

| Agente | O que faz |
| --- | --- |
| Fábio · Gestor | Responde você e passa tarefas para quem da equipe pode fazer. É o encarregado: quando você pergunta por que uma tarefa demorou ou não foi feita, ele explica o motivo e diz como destravar. A cada 2 minutos ele vigia a equipe e te avisa sozinho de tarefa travada, com erro ou parada sem dono (o aviso aparece na tela e na conversa com ele). |
| Ana · Comercial | Lê o WhatsApp comercial (pela Evolution ou pela tela do WhatsApp Web aberta num PC), aponta quem está esperando resposta e quem está no ponto de follow-up da régua R1–R5, e escreve as mensagens sugeridas. Ela **nunca envia** mensagem: só sugere, quem envia é a Mari. |
| Carla · Conteúdo e vídeos | Escreve carrosséis, roteiros e legendas, e monta vídeos no editor **Abekyo** (Remotion), que fica aberto no PC 3: monta o projeto, confere, renderiza o MP4 e abre o vídeo numa guia do PC dela. Peça ajustes que ela refaz, ou edite à mão no editor. |

### Os agentes enxergam e usam as telas

Os agentes trabalham usando os computadores. A cada poucos segundos o escritório lê o que está na frente de cada tela (PCs, TV e Spotify) e manda para o n8n, então qualquer agente responde na hora perguntas como *"o que tem no PC 4?"* ou *"quem mandou a última mensagem no WhatsApp?"*. Para ir além, eles podem usar as telas com as ferramentas **ver_telas** e **usar_tela**: ler a página, clicar num texto ou no número de um item da lista, rolar, abrir um endereço numa guia nova, trocar de guia, voltar, digitar, **perguntar** (escreve na IA aberta na tela, como o Claude, envia e espera a resposta) e esperar.

Cada agente tem o seu PC: Ana = PC 1, Carla = PC 3 e Fábio = PC 6. Peça, por exemplo: *"Fábio, entra no Claude no seu PC e peça um plano de posts da semana; me diga o que ele respondeu"*. O Fábio abre o claude.ai no PC dele, escreve o pedido, espera o Claude terminar (até uns 2 minutos; se demorar mais, ele espera e lê de novo) e te conta o que o Claude respondeu e fez. Para isso, o Claude precisa estar logado no Chrome. Exemplo: *"Fábio, tem um PC com o WhatsApp aberto, peça para a Ana resumir a primeira conversa"*. A Ana anda até o PC, a tela ganha uma moldura com o nome dela, ela clica na primeira conversa, lê as mensagens e responde.

- **No WhatsApp Web eles só leem:** digitar fica bloqueado pela extensão.
- **Responder clientes com um clique:** peça para a Ana mandar ou responder alguém. Ela prepara um **cartão de envio** no chat (contato, número e a mensagem, que você pode editar). Você confere e aperta **Enviar pelo WhatsApp**, confirma, e a mensagem sai pelo WhatsApp comercial, pela Evolution, sem usar as telas dos PCs. A Ana nunca envia sozinha: só sai o que você aprova. O envio usa um código desta instalação, que só a página do escritório conhece.
- **Deixe o WhatsApp Web aberto em uma guia só:** o WhatsApp não funciona em duas guias ao mesmo tempo (a segunda mostra "Sorry, something went wrong").
- **Eles aprendem com você:** diga "a partir de agora…", "sempre…" ou "nunca mais…" e o agente guarda a instrução e segue em todos os próximos pedidos. No painel de cada agente aparece "O que ele aprendeu", com **+ ensinar** e o **×** para esquecer.
- **Você acompanha enquanto trabalham:** o chat mostra ao vivo cada passo nas telas (⏳ fazendo, ✓ deu certo, ✗ não deu), e o agente manda recados no meio de tarefas longas. Se ele tentar demais sem conseguir, para e explica os últimos passos (em vez de "Agent stopped due to max iterations").
- **Navegadores mais livres:** os sites abertos nas telas são pedidos como numa aba comum, e os logins deles passam a funcionar dentro das telas. Se algum site ainda não funcionar dentro da tela, o botão **↗** na barra da tela abre a guia numa aba do Chrome de verdade.
- A Carla cria as imagens dos carrosséis e vídeos sozinha (ferramenta **criar_imagem**, pelo gerador grátis pollinations.ai) e já coloca no editor de vídeo.
- Precisa do escritório aberto no Chrome com a extensão (versão 1.7.0): é a extensão que lê e clica dentro das telas. Desde a 1.5.0 as telas conversam com o escritório por dentro da extensão, o que fez a leitura do WhatsApp Web funcionar.
- As respostas dos agentes aparecem formatadas no chat (parágrafos, listas, negrito e tabelas).
- Como funciona: o escritório manda ao n8n o mapa das telas; o pedido do agente entra numa fila no Central (tabela **escritorio_comandos**); o escritório pega o pedido, faz na tela e devolve o resultado, que volta para o agente.

### Editor de vídeo da Carla (Abekyo)

A Carla usa o [abekyo-editor](https://github.com/abekyo/abekyo-editor) (licença MIT), que já vem dentro da pasta do escritório (`abekyo-editor`) e roda neste PC em http://localhost:3000. O `instalar.bat` faz o `npm install` na primeira vez (alguns minutos) e liga o editor numa janela própria; depois, o `abrir-escritorio.bat` liga o editor sozinho. O PC 3 do escritório ganha uma guia com o editor.

**A tela do PC 3 ficou com uma folhinha triste?** O editor está desligado (o escritório também avisa ao abrir). Abra pelo `abrir-escritorio.bat` ou, na pasta do abekyo-editor, rode `npm run dev`. Sem o editor, a Carla continua escrevendo roteiros e carrosséis, mas não renderiza vídeos.

**Como usar:** clique no boneco. Abre a conversa com ele, com a tarefa atual e o último resultado. O boneco senta no PC enquanto trabalha, vai para a pausa quando termina e fica vermelho se der erro. Quando alguém termina, aparece um aviso na tela. As etiquetas dos agentes de verdade têm **IA**, e o botão **Agentes** em cima mostra se o n8n está conectado (clique nele para trocar o endereço do n8n).

### Painel comercial (segunda tela da Ana)

Na mesa da Ana (PC 1) há uma segunda tela com o **painel comercial**. Também dá para abrir a página `painel-comercial.html` direto: clique na tela, ou abra http://127.0.0.1:8765/painel-comercial.html. O painel tem:

- **Régua de follow-up ao vivo**: os leads aparecem em D0, R1 (D+1), R2 (D+2), R3 (D+4), R4 (D+7) e R5 (D+14), contando desde a nossa mensagem que ficou sem resposta. As conversas são lidas do WhatsApp comercial pela Evolution. Clique numa etapa para ver só ela.
- **Esperando resposta**: o cliente falou por último. Fica crítico (⚠) com mais de 24h sem resposta ou com assunto delicado (reembolso, cancelamento, reclamação, cão machucado ou doente).
- **Quem recebe o quê no Telegram**: Mari (SDR, todo dia), Gustavo (vendedor, todo dia), Rosângela (só caso crítico) e Wes (por último: crítico aberto 20h depois do aviso à Rosângela, ou WhatsApp desconectado). A mensagem de cada um já vem montada. Você confere, ajusta e aperta **Enviar**.
- **Configurar** (no fim do painel):
  1. Crie um bot no Telegram com o @BotFather e cole o token.
  2. Peça para cada pessoa mandar um "oi" para o bot e clique em **Descobrir IDs** para ligar cada ID à pessoa.
  3. Se quiser, ligue o **envio diário às 8h30**: Mari e Gustavo sempre; Rosângela e Wes só quando houver algo. Ele vem desligado.
- Tudo roda no fluxo **Escritório · Painel comercial** do n8n. O token e os IDs ficam na tabela de dados `escritorio_config`, e cada envio fica no histórico do painel.

### WhatsApp comercial (Evolution)

A Evolution do escritório vem pronta em [`servidor/evolution`](servidor/evolution) (Evolution API v2 + banco Postgres, no Docker, em http://localhost:8080). O instalador cria a chave dela (arquivo `servidor/evolution/.env`, que fica só no seu PC), sobe os containers, cria a instância `cantinho-comercial` e abre uma página com o QR code, que se renova sozinha até o celular conectar. Se o WhatsApp desconectar, o `abrir-escritorio.bat` mostra o QR code de novo. Se já existir outra Evolution no seu Docker, ele usa a que existe. O **PC 1** ganha uma guia com o painel da Evolution (http://localhost:8080/manager); para entrar, use o Server URL e a API Key do arquivo `whatsapp-evolution.txt` que o instalador cria na pasta (não compartilhe a chave). A Ana só **lê** as conversas; quem envia é a Mari.

### Instalar os fluxos no n8n

O **`instalar.bat`** faz tudo isto sozinho (veja **Como instalar e abrir**). Se preferir fazer à mão, ou se o instalador não achar o n8n no Docker:

1. No n8n, importe os 4 arquivos da pasta [`n8n`](n8n): **Escritório · Central dos agentes**, **Escritório · Fábio (Gestor)**, **Escritório · Ana (Comercial)** e **Escritório · Carla (Conteúdo e vídeos)** (menu **⋯ → Import from File**).
2. Nos fluxos do Fábio, da Ana e da Carla, abra o nó **Cérebro** e escolha a credencial do Ollama (endereço `http://127.0.0.1:11434`). A lista de modelos fica no topo do código dos nós **Escolher cérebro** e **Trocar cérebro** (`const CEREBROS = [...]`).
3. No fluxo da Ana, abra o nó **Preparar** e preencha no topo do código:
   - `EVOLUTION_URL`: o endereço da Evolution visto de dentro do n8n (o mesmo que o fluxo 4 do agente comercial usa, por exemplo `http://evolution-api:8080`).
   - `EVOLUTION_KEY`: a apikey da Evolution.
   - `INSTANCIA`: já vem `cantinho-comercial`.
4. **Ative (publique)** os 4 fluxos. Sem isso os webhooks não respondem.
5. Abra o escritório. O botão em cima deve mostrar **Agentes: Ana, Carla e Fábio de verdade**. Se o seu n8n não está em `http://localhost:5678`, clique no botão e coloque o endereço.

O Central cria sozinho, na primeira vez, a tabela de dados **escritorio_registro**, onde fica cada aviso dos agentes (estado, conversas, cartões do kanban e avisos do mural).

### Quadro de tarefas (kanban)

O quadro grande da parede do fundo mostra as tarefas da equipe em 4 colunas: **A fazer**, **Fazendo**, **Feito** e **Com erro**. Os cartões andam sozinhos: quando um agente começa uma tarefa, o cartão vai para Fazendo; quando termina, para Feito (com o resultado) ou Com erro. Tarefa que o Fábio passa para quem ainda não tem fluxo fica em A fazer.

Clique no quadro para abrir a versão interativa:

- **+ Nova tarefa:** escreva, escolha o agente e, se ele for de verdade, marque *pedir para fazer agora*. Sem marcar, o cartão fica em A fazer.
- **Arrastar** um cartão para outra coluna, ou clicar nele e usar **Mover para**.
- No cartão: o resultado, **Pedir para (agente) fazer agora** e **Conversar com (agente)**.
- Filtro por agente no topo.

Sem o n8n, o quadro mostra as tarefas simuladas, só para ver.

### Mural de avisos

O quadro de cortiça da parede da esquerda é um mural de post-its. Clique nele para escrever um aviso (Enter cola), escolher a cor ou tirar um aviso. Com o n8n ligado, o mural é compartilhado com os agentes: o Fábio lê os avisos antes de responder e cola avisos quando você pede (*"Fábio, coloca no mural que sexta tem reunião"*). Sem o n8n, os avisos ficam só neste navegador.

### Como os agentes conversam

Tudo passa por webhooks do n8n:

| Webhook | Quem chama | Para quê |
| --- | --- | --- |
| `GET /webhook/escritorio/estado` | o escritório, a cada 3 s | estado, conversas, cartões do kanban e mural |
| `POST /webhook/escritorio/<agente>` | o escritório ou o Fábio | pedido para o agente (`texto`, `de`); ele responde na hora e trabalha depois |
| `POST /webhook/escritorio/evento` | os agentes e o escritório | avisar `trabalhando`, `livre`, `erro` ou `aguardando` (com a tarefa, o resultado, a mensagem e o `card`), mover cartão (`card` + `coluna`) e escrever ou tirar aviso do mural (`agente: mural`) |

Os fluxos são gerados por `tools/gerar-fluxos-n8n.py`. Para criar um agente novo: copie o molde do Fábio ou da Ana no gerador (webhook `escritorio/<id>`, avisos para o Central), coloque o id dele em `AGENTES_REAIS` no nó **Montar estado** do Central e gere de novo com `python tools/gerar-fluxos-n8n.py`.

## O que é simulado

- Bruno, Davi e Eva, e as tarefas deles, são dados de exemplo gerados na própria página (Fábio, Ana e Carla são de verdade quando o n8n está ligado; sem o n8n, todos voltam a ser simulados).
- O mapa do Segundo Cérebro é uma foto das notas e dos links `[[...]]` lidos em 20/10/2026. Ele não se atualiza sozinho.

## Atualizar o mapa do Segundo Cérebro

`tools/gerar-grafo.py` lê uma pasta de notas Markdown e gera um JSON com as notas e os links `[[...]]` entre elas:

```bash
python tools/gerar-grafo.py "C:\caminho\para\segundo cerebro" grafo.json
```

Hoje os dados do mapa (`FOLDERS`, `NOTES` e `LINKS`) ficam escritos à mão no topo do script da página. O próximo passo é a página ler esse JSON diretamente.

## Próximos passos

- Dar fluxo para os outros agentes: Bruno (leads), Davi (agenda) e Eva (relatórios).
- Abrir no editor do Abekyo o projeto que a Carla montou (hoje o editor não tem como carregar um projeto pronto: ela renderiza e mostra o MP4).
- Fazer o mapa ler o JSON gerado pelo script, sem editar o HTML.
