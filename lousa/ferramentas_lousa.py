#!/usr/bin/env python3
"""Ferramentas do Claude para ler e responder a Lousa de Ideias.

A lousa guarda a conversa como JSON dentro da própria página, em
<script type="application/json" id="dados">. Quando a lousa se republica
(você tocou em Enviar), o Claude lê a versão publicada, olha o desenho e
publica a página de novo com a resposta.

Uso:
  ferramentas_lousa.py corpo   <pagina_lida.html> <saida.html>
      Tira o esqueleto (doctype/head) que a plataforma acrescenta e grava só o
      conteúdo que o Artifact publica.
  ferramentas_lousa.py listar  <pagina.html>
      Mostra as mensagens (id, autor, hora, texto, imagem).
  ferramentas_lousa.py imagem  <pagina.html> <id_mensagem> <saida.png>
      Grava a imagem embutida (data: URL) de uma mensagem, quando houver.
  ferramentas_lousa.py responder <corpo.html> <arquivo_texto> [--imagem ID_ASSET]
      Acrescenta uma mensagem do Claude ao JSON da página (no próprio arquivo).
"""
import base64
import datetime
import json
import re
import secrets
import sys

PADRAO_DADOS = re.compile(r'(<script type="application/json" id="dados">)(.*?)(</script>)', re.S)


def ler(caminho):
    with open(caminho, encoding='utf-8') as f:
        return f.read()


def gravar(caminho, texto):
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write(texto)


def corpo_da_pagina(html):
    """Devolve o conteúdo entre o <body> do esqueleto e o </body></html> final."""
    if not html.lstrip().lower().startswith('<!doctype'):
        return html
    inicio = html.find('<body>')
    fim = html.rfind('</body></html>')
    if inicio < 0 or fim < 0 or fim < inicio:
        raise SystemExit('Não encontrei o esqueleto <body>…</body></html> na página.')
    corpo = html[inicio + len('<body>'):fim]
    # a plataforma acrescenta uma quebra de linha logo depois de <body> e outra antes de </body>
    if corpo.startswith('\n'):
        corpo = corpo[1:]
    if corpo.endswith('\n'):
        corpo = corpo[:-1]
    return corpo


def ler_dados(html):
    m = PADRAO_DADOS.search(html)
    if not m:
        raise SystemExit('A página não tem o bloco de dados da lousa.')
    return m, json.loads(m.group(2))


def escrever_dados(html, m, dados):
    bloco = json.dumps(dados, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return html[:m.start(2)] + bloco + html[m.end(2):]


def main(args):
    if not args:
        raise SystemExit(__doc__)
    cmd = args[0]
    if cmd == 'corpo':
        gravar(args[2], corpo_da_pagina(ler(args[1])))
        print('ok:', args[2])
    elif cmd == 'listar':
        _, dados = ler_dados(ler(args[1]))
        for msg in dados.get('mensagens', []):
            img = msg.get('imagem') or ('(embutida)' if msg.get('imagemDados') else '-')
            texto = (msg.get('texto') or '').replace('\n', ' / ')
            print(f"{msg.get('id')} | {msg.get('de')} | {msg.get('em')} | imagem={img} | {texto}")
    elif cmd == 'imagem':
        _, dados = ler_dados(ler(args[1]))
        alvo = next((x for x in dados.get('mensagens', []) if x.get('id') == args[2]), None)
        if not alvo or not alvo.get('imagemDados'):
            raise SystemExit('Mensagem sem imagem embutida (use o id do asset com o Artifact).')
        cabecalho, b64 = alvo['imagemDados'].split(',', 1)
        with open(args[3], 'wb') as f:
            f.write(base64.b64decode(b64))
        print('ok:', args[3], cabecalho)
    elif cmd == 'responder':
        caminho, texto = args[1], ler(args[2]).strip()
        imagem = None
        if '--imagem' in args:
            imagem = args[args.index('--imagem') + 1]
            if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', imagem):
                raise SystemExit('Id de asset inválido.')
        html = ler(caminho)
        m, dados = ler_dados(html)
        instante = datetime.datetime.now(datetime.timezone.utc)
        agora = instante.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (instante.microsecond // 1000)
        msg = {'id': 'c' + secrets.token_hex(6), 'de': 'claude', 'em': agora, 'texto': texto}
        if imagem:
            msg['imagem'] = imagem
        dados.setdefault('mensagens', []).append(msg)
        dados['versao'] = 1
        gravar(caminho, escrever_dados(html, m, dados))
        print('resposta adicionada:', msg['id'])
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
