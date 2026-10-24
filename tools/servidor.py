# Servidor local do escritório (http://127.0.0.1:8765), usado pelo abrir-escritorio.bat.
# Diferente do "python -m http.server": manda o Chrome nunca guardar cópia das páginas (assim uma pasta atualizada
# aparece na hora) e, antes de ligar, fecha um servidor antigo que tenha ficado aberto (de uma pasta velha).
import http.server, os, socket, subprocess, sys, time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTA = 8765


def porta_ocupada():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', PORTA)) == 0


def fechar_servidor_antigo():
    if not porta_ocupada(): return
    if os.name == 'nt':
        r = subprocess.run(['netstat', '-ano', '-p', 'TCP'], capture_output=True, text=True, errors='replace')
        for linha in r.stdout.splitlines():
            p = linha.split()
            if len(p) >= 5 and p[1].endswith(f':{PORTA}') and p[3].upper() in ('LISTENING', 'ESCUTANDO') and p[4] != str(os.getpid()):
                subprocess.run(['taskkill', '/PID', p[4], '/T', '/F'], capture_output=True)
    else:
        r = subprocess.run(['lsof', '-ti', f'tcp:{PORTA}', '-sTCP:LISTEN'], capture_output=True, text=True)
        for pid in r.stdout.split():
            try: os.kill(int(pid), 15)
            except Exception: pass
    for _ in range(20):
        if not porta_ocupada(): return
        time.sleep(0.3)


# arquivos com chaves deste PC: só a própria página do escritório pode ler (outro site aberto no Chrome não)
PRIVADOS = ('/escritorio-config.js', '/escritorio-local.json', '/whatsapp-evolution.txt', '/servidor/evolution/.env')


class SemCache(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        caminho = self.path.split('?', 1)[0]
        if caminho in PRIVADOS:
            if caminho != '/escritorio-config.js' or self.headers.get('Sec-Fetch-Site', 'same-origin') not in ('same-origin', 'none'):
                self.send_error(403); return
        super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    fechar_servidor_antigo()
    os.chdir(RAIZ)
    print(f'Escritório 3D em http://127.0.0.1:{PORTA}/escritorio-3d.html (pasta {RAIZ}). Feche esta janela para desligar.', flush=True)
    http.server.ThreadingHTTPServer(('127.0.0.1', PORTA), SemCache).serve_forever()
