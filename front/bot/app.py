from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path
import requests
import time
import os
import signal
import psutil
import threading
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///Morador.db'
db = SQLAlchemy(app)
is_whatsapp_connected = False
cadastro_ativo_via_mensagem = False

class Morador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bloco = db.Column(db.String(50), nullable=False)
    apartamento = db.Column(db.String(50), nullable=False)
    contato = db.Column(db.String(100), nullable=False)
    ultima_notificacao = db.Column(db.DateTime, nullable=True)
    encomenda_pendente = db.Column(db.Boolean, default=False)



# Criação do banco de dados
with app.app_context():
    db.create_all()


def update_whatsapp_status():
    global is_whatsapp_connected
    try:
        time.sleep(5)
        response = requests.get('http://localhost:3000/qr-code', timeout=5)
        qr_code_html = response.text
        is_whatsapp_connected = qr_code_html == 'Nenhum QR Code disponível no momento.'
    except requests.exceptions.RequestException:
        is_whatsapp_connected = False


@app.route('/whatsapp-status', methods=['GET'])
def whatsapp_status():
    update_whatsapp_status()
    return {'connected': is_whatsapp_connected}


# ========= Rota Principal ===========
@app.route('/')
def home():
    if not is_whatsapp_connected:
        return redirect(url_for('mostrar_qr'))
    else:
        return redirect(url_for('notificacao'))

@app.context_processor
def inject_cadastro_status():
    global cadastro_ativo_via_mensagem
    return {"cadastro_ativo": cadastro_ativo_via_mensagem}

@app.route('/toggle-cadastro-mensagem', methods=['POST'])
def toggle_cadastro_mensagem():
    global cadastro_ativo_via_mensagem
    cadastro_ativo_via_mensagem = not cadastro_ativo_via_mensagem
    estado = "ativado" if cadastro_ativo_via_mensagem else "desativado"
    flash(f"Cadastro automático via mensagem foi {estado}{', comunique com a portaria para reativar ou realizar o cadastro.' if estado == 'desativado' else ''}")
    return redirect(request.referrer or '/')

@app.route('/mostrar_qr')
def mostrar_qr():
    try:
        time.sleep(5)
        response = requests.get('http://localhost:3000/qr-code')
        qr_code_html = response.text
        if qr_code_html == 'Nenhum QR Code disponível no momento.':
            return redirect(url_for('notificacao'))
    except requests.exceptions.RequestException:
        qr_code_html = "<p>Erro ao conectar com o servidor Node.js. Certifique-se de que está rodando.</p>"
    return render_template('qr_display.html', qr_code_html=qr_code_html, conectado=is_whatsapp_connected)


@app.route('/historico-notificacoes')
def historico_notificacoes():
    moradores = Morador.query.filter_by(encomenda_pendente=True).order_by(Morador.bloco, Morador.apartamento).all()
    return render_template('historico_notificacoes.html', moradores=moradores, conectado=is_whatsapp_connected)


# ========= Rota para Cadastro ===========
@app.route('/cadastro')
def cadastro():
    blocos_predefinidos = [f'Bloco {i}' for i in range(1, 10)]
    apartamentos_predefinidos = [f"Apartamento {i}0{j}" for i in range(1, 6) for j in range(1, 5)]
    return render_template('cadastro.html', blocos=blocos_predefinidos, apartamentos=apartamentos_predefinidos,
                           conectado=is_whatsapp_connected)


@app.route('/adicionar', methods=['POST'])
def adicionar_morador():
    global contato, contatos, cadastro_ativo_via_mensagem

    if request.is_json:
        if not cadastro_ativo_via_mensagem:
            return jsonify({"error": "Cadastro automático via mensagem está desativado."}), 403
        data = request.get_json()
        bloco = data.get('bloco')
        apartamento = data.get('apartamento')
        contato = data.get('contato')
    else:

        bloco = request.form.get('bloco')
        apartamento = request.form.get('apartamento')
        contatos = request.form.getlist('contato')
        print(f"bloco: {bloco}")
        print(f"apartamento: {apartamento}")
        print(f"contatos: {contatos}")

    if bloco and apartamento:
        if request.is_json:
            morador_existente = Morador.query.filter_by(bloco=bloco, apartamento=apartamento, contato=contato).first()
            if not morador_existente:
                novo_morador = Morador(bloco=bloco, apartamento=apartamento, contato=contato)
                db.session.add(novo_morador)
                db.session.commit()
                flash('Morador cadastrado com sucesso!')
            else:
                flash('Este morador já está cadastrado.')
        else:
            for contato in contatos:
                if len(contato) > 0:
                    try:
                        _contato = int(contato.strip())
                    except ValueError:
                        flash('Contato deve conter apenas números.')
                    print(f"contato: {contato}")
                    morador_existente = Morador.query.filter_by(bloco=bloco, apartamento=apartamento, contato=contato).first()
                    if not morador_existente:
                        novo_morador = Morador(bloco=bloco, apartamento=apartamento, contato=contato.strip())
                        db.session.add(novo_morador)
                    else:
                        flash(f'O contato {contato} já está cadastrado para o {bloco} - {apartamento}.')
            db.session.commit()
            flash('Cadastro atualizado com novos moradores!')
        if request.is_json:
            return jsonify({"message": "Morador cadastrado com sucesso!"}), 201
        else:
            return redirect(url_for('cadastro'))
    else:
        if request.is_json:
            return jsonify({"error": "Por favor, preencha todos os campos corretamente!"}), 400
        else:
            flash('Por favor, preencha todos os campos corretamente!')
            return redirect(url_for('cadastro'))


# ========= Rota para Remover Morador ===========
@app.route('/remover', methods=['GET', 'POST'])
def remover_morador():
    # Obter blocos e apartamentos cadastrados
    blocos = db.session.query(Morador.bloco).distinct().all()
    blocos = [bloco[0] for bloco in blocos]
    apartamentos_por_bloco = {
        bloco: db.session.query(Morador.apartamento).filter_by(bloco=bloco).distinct().all()
        for bloco in blocos
    }
    apartamentos_por_bloco = {bloco: [apt[0] for apt in apts] for bloco, apts in apartamentos_por_bloco.items()}

    if request.method == 'POST':
        bloco = request.form.get('bloco')
        apartamento = request.form.get('apartamento')

        if bloco and apartamento:
            # Remover contatos do bloco e apartamento selecionados
            Morador.query.filter_by(bloco=bloco, apartamento=apartamento).delete()
            db.session.commit()
            flash(f"Todos os contatos do {bloco} - {apartamento} foram removidos com sucesso.")
        else:
            flash("Por favor, selecione um bloco e um apartamento válidos.")

        return redirect(url_for('remover_morador'))

    return render_template(
        'remover.html',
        blocos=blocos,
        apartamentos_por_bloco=apartamentos_por_bloco,
        conectado=is_whatsapp_connected
    )


# ========= Rota para Modificar Contatos ===========
@app.route('/modificar', methods=['GET', 'POST'])
def modificar_contatos():
    # Obter blocos únicos cadastrados
    blocos = db.session.query(Morador.bloco).distinct().all()
    blocos = [bloco[0] for bloco in blocos]  # Converter em lista simples

    # Obter apartamentos cadastrados por bloco
    apartamentos_por_bloco = {
        bloco: db.session.query(Morador.apartamento).filter_by(bloco=bloco).distinct().all()
        for bloco in blocos
    }
    # Converter os resultados para listas simples
    _apartamentos_por_bloco = {bloco: [apt[0] for apt in apartamentos] for bloco, apartamentos in apartamentos_por_bloco.items()}

    # Log para verificar o formato dos dados
    print("Blocos disponíveis:", blocos)
    print("Apartamentos por Bloco:", _apartamentos_por_bloco)

    # Dados do formulário
    bloco_selecionado = request.form.get('bloco')
    apartamento_selecionado = request.form.get('apartamento')

    # Buscar moradores do bloco e apartamento selecionados
    moradores = []
    if bloco_selecionado and apartamento_selecionado:
        moradores = Morador.query.filter_by(bloco=bloco_selecionado, apartamento=apartamento_selecionado).all()

    return render_template(
        'modificar.html',
        blocos=blocos,
        apartamentos_por_bloco=_apartamentos_por_bloco,
        bloco_selecionado=bloco_selecionado,
        apartamento_selecionado=apartamento_selecionado,
        moradores=moradores,
        conectado=is_whatsapp_connected
    )

@app.route('/atualizar_contatos', methods=['POST'])
def atualizar_contatos():
    bloco = request.form.get('bloco')
    apartamento = request.form.get('apartamento')
    contatos_ids = request.form.getlist('contato_id')
    novos_contatos = request.form.getlist('contato')

    # Atualizar contatos
    for contato_id, novo_contato in zip(contatos_ids, novos_contatos):
        if novo_contato:
            morador = Morador.query.get(contato_id)
            morador.contato = novo_contato
        else:
            Morador.query.filter_by(id=contato_id).delete()

    db.session.commit()
    flash(f"Contatos atualizados com sucesso para {bloco} - {apartamento}.")
    return redirect(url_for('modificar_contatos'))


# ========= Rota para Enviar Notificação ===========
@app.route('/notificacao')
def notificacao():
    # Obter blocos e apartamentos cadastrados
    blocos = db.session.query(Morador.bloco).distinct().all()
    blocos = [bloco[0] for bloco in blocos]  # Converter para lista simples
    apartamentos_por_bloco = {
        bloco: db.session.query(Morador.apartamento).filter_by(bloco=bloco).distinct().all()
        for bloco in blocos
    }
    # Converter para um dicionário simples
    apartamentos_por_bloco = {
        bloco: [apt[0] for apt in apartamentos] for bloco, apartamentos in apartamentos_por_bloco.items()
    }

    return render_template('notificacao.html', blocos=blocos, apartamentos_por_bloco=apartamentos_por_bloco, conectado=is_whatsapp_connected)


@app.route('/enviar_notificacao', methods=['POST'])
def enviar_notificacao():
    bloco = request.form.get('bloco')
    apartamento = request.form.get('apartamento')
    mensagem_padrao = f"""📦 *Aviso Importante: Encomenda Disponível!*\n
Prezado morador do *{bloco} - {apartamento}*,

Informamos que há uma encomenda disponível para retirada na portaria.

✅ *O que fazer?*
- Por favor, compareça à portaria o mais breve possível para retirar sua encomenda.
- Após a retirada, você pode enviar a palavra *_retirada_* nesta conversa para confirmar a retirada, ou solicitar ao porteiro que marque a encomenda como retirada no sistema.

Agradecemos sua colaboração! 
📍 _Portaria_
"""
    # Buscar contatos relacionados
    _Morador = Morador.query.filter_by(bloco=bloco, apartamento=apartamento).all()
    if not _Morador:
        flash('Nenhum contato encontrado para esse apartamento.')
        return redirect(url_for('notificacao'))

    # Enviar notificação para cada contato
    for morador in _Morador:
        payload = {"contato": morador.contato, "mensagem": mensagem_padrao}
        try:
            resp = requests.post('http://localhost:3000/enviar-mensagem', json=payload)
            if resp.status_code == 500:
                return redirect(url_for('mostrar_qr'))
            elif resp.status_code == 200:
                # Atualizar a data e hora da última notificação e marcar como pendente
                morador.ultima_notificacao = datetime.now()
                morador.encomenda_pendente = True
                db.session.commit()
                flash(f"Mensagem enviada para {bloco} - {apartamento}")
            else:
                flash(f"Erro ao enviar mensagem: {resp.text}")
        except Exception as e:
            flash(f"Erro ao enviar mensagem: {str(e)}")
            return redirect(url_for('mostrar_qr'))
    return redirect(url_for('notificacao'))

@app.route('/enviar_notificacao_em_grupo', methods=['POST'])
def enviar_notificacao_em_grupo():
    destinatarios = request.form.getlist('destinatarios')

    if not destinatarios:
        flash("Por favor, selecione pelo menos um destinatário.")
        return redirect(url_for('notificacao'))

    for destinatario in destinatarios:
        bloco, apartamento = destinatario.split('|')
        mensagem_padrao = f"""📦 *Aviso Importante: Encomenda Disponível!*\n
Prezado morador do *{bloco} - {apartamento}*,

Informamos que há uma encomenda disponível para retirada na portaria.

✅ *O que fazer?*
- Por favor, compareça à portaria o mais breve possível para retirar sua encomenda.
- Após a retirada, você pode enviar a palavra *_retirada_* nesta conversa para confirmar a retirada, ou solicitar ao porteiro que marque a encomenda como retirada no sistema.

Agradecemos sua colaboração! 
📍 _Portaria_
"""
        # Buscar moradores relacionados
        moradores = Morador.query.filter_by(bloco=bloco, apartamento=apartamento).all()

        if not moradores:
            flash(f"Não há moradores cadastrados no {bloco} - {apartamento}.")
            continue

        # Enviar notificações para cada morador
        for morador in moradores:
            payload = {"contato": morador.contato, "mensagem": mensagem_padrao}
            try:
                resp = requests.post('http://localhost:3000/enviar-mensagem', json=payload)
                if resp.status_code == 200:
                    morador.ultima_notificacao = datetime.now()
                    morador.encomenda_pendente = True
                    db.session.commit()
                else:
                    flash(f"Erro ao enviar mensagem para {morador.contato}: {resp.text}")
            except Exception as e:
                flash(f"Erro ao enviar mensagem para {morador.contato}: {str(e)}")

    flash("Notificações enviadas com sucesso!")
    return redirect(url_for('notificacao'))




@app.route('/remover-encomenda/<contato>', methods=['POST'])
def remover_encomenda(contato):
    morador = Morador.query.filter_by(contato=contato, encomenda_pendente=True).first()
    if morador:
        morador.encomenda_pendente = False
        db.session.commit()
        return jsonify({"message": f"Encomenda do {morador.bloco} - {morador.apartamento} foi marcada como retirada."}), 200
    else:
        return jsonify({"error": "Nenhuma encomenda pendente encontrada para este contato."}), 404

@app.route('/remover-encomenda-porteiro/<int:id>', methods=['POST'])
def remover_encomenda_porteiro(id):
    morador = Morador.query.get_or_404(id)
    if morador.encomenda_pendente:
        morador.encomenda_pendente = False
        db.session.commit()

        # Enviar notificação para todos os contatos do bloco e apartamento
        moradores_no_apartamento = Morador.query.filter_by(
            bloco=morador.bloco, apartamento=morador.apartamento
        ).all()
        for contato_morador in moradores_no_apartamento:
            mensagem = f"📦 Olá! A encomenda no {morador.bloco} - {morador.apartamento} foi registrada como retirada."
            try:
                requests.post(
                    'http://localhost:3000/enviar-mensagem',
                    json={"contato": contato_morador.contato, "mensagem": mensagem}
                )
            except Exception as e:
                print(f"Erro ao enviar notificação para {contato_morador.contato}: {e}")

        flash(f"A notificação foi enviada para todos os moradores do {morador.bloco} - {morador.apartamento}.")
    else:
        flash("Nenhuma encomenda pendente encontrada para este morador.")
    return redirect(url_for('historico_notificacoes'))



@app.route('/fechar')
def fechar_sistema():
    try:
        requests.get('http://localhost:3000/encerrar')
    except Exception:
        pass
    current_pid = os.getpid()
    parent = psutil.Process(current_pid)
    for child in parent.children(recursive=True):
        child.terminate()
    os.kill(current_pid, signal.SIGTERM)
    return "Sistema encerrado com sucesso."


# ========= Iniciar o Servidor ===========
if __name__ == '__main__':
    caminho_pasta = Path("C:/NotificacaoEncomenda/back/tokens")
    if caminho_pasta.exists() and caminho_pasta.is_dir():
        status_thread = threading.Thread(target=update_whatsapp_status, daemon=True)
        status_thread.start()
    app.run(debug=True)
