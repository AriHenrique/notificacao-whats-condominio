from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path
import requests
import time
import os
import signal
import psutil
import threading
from datetime import datetime, timedelta, timezone
import io
import csv


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


class HistoricoRegistro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    bloco = db.Column(db.String(50), nullable=False)
    apartamento = db.Column(db.String(50), nullable=False)
    contato = db.Column(db.String(100), nullable=True)
    mensagem = db.Column(db.Text, nullable=True)
    data_registro = db.Column(db.DateTime, default=lambda: datetime.now(timezone(timedelta(hours=-3))))
    registrado_por = db.Column(db.String(50), nullable=False)
    observacao = db.Column(db.Text, nullable=True)


# Criação do banco de dados
with app.app_context():
    db.create_all()


# def verificar_envio_periodico():
#     global is_whatsapp_connected
#     try:
#         payload = {
#             "contato": "3184787489",
#             "mensagem": "Mensagem de teste para verificar conexão com WhatsApp."
#         }
#         response = requests.post('http://localhost:3000/enviar-mensagem', json=payload)
#         if response.status_code == 200:
#             is_whatsapp_connected = True
#             print("[INFO] WhatsApp conectado e envio funcionando.")
#         else:
#             is_whatsapp_connected = False
#             print(f"[ERRO] Envio falhou: {response.text}")
#     except requests.exceptions.RequestException as e:
#         print(f"[ERRO] Não foi possível conectar ao WhatsApp: {str(e)}")
#     return is_whatsapp_connected

def update_whatsapp_status():
    global is_whatsapp_connected
    try:
        time.sleep(5)
        response = requests.get('http://localhost:3000/health')
        is_whatsapp_connected = response.status_code == 200
    except requests.exceptions.RequestException:
        is_whatsapp_connected = False
    return is_whatsapp_connected


@app.route('/whatsapp-status', methods=['GET'])
def whatsapp_status():
    if not update_whatsapp_status():
        return redirect(url_for('mostrar_qr'))
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
    flash(
        f"Cadastro automático via mensagem foi {estado}{', comunique com a portaria para reativar ou realizar o cadastro.' if estado == 'desativado' else ''}")
    return redirect(request.referrer or '/')


@app.route('/mostrar_qr')
def mostrar_qr():
    global is_whatsapp_connected
    try:
        time.sleep(5)
        response = requests.get('http://localhost:3000/qr-code')
        qr_code_html = response.text
        if qr_code_html == 'Nenhum QR Code disponível no momento.':
            is_whatsapp_connected = True
            return redirect(url_for('notificacao'))
        else:
            is_whatsapp_connected = False
    except requests.exceptions.RequestException:
        qr_code_html = "<p>Erro ao conectar com o servidor Node.js. Certifique-se de que está rodando.</p>"
    return render_template('qr_display.html', qr_code_html=qr_code_html, conectado=is_whatsapp_connected)


@app.route('/historico-notificacoes')
def historico_notificacoes():
    moradores = Morador.query.filter_by(encomenda_pendente=True).all()
    blocos_apartamentos = {
        (morador.bloco, morador.apartamento): morador for morador in moradores
    }
    moradores_unicos = list(blocos_apartamentos.values())

    return render_template(
        'historico_notificacoes.html', moradores=moradores_unicos, conectado=is_whatsapp_connected
    )


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
                    morador_existente = Morador.query.filter_by(bloco=bloco, apartamento=apartamento,
                                                                contato=contato).first()
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
    blocos = db.session.query(Morador.bloco).distinct().all()
    blocos = [bloco[0] for bloco in blocos]
    apartamentos_por_bloco = {
        bloco: db.session.query(Morador.apartamento).filter_by(bloco=bloco).distinct().all()
        for bloco in blocos
    }
    _apartamentos_por_bloco = {bloco: [apt[0] for apt in apartamentos] for bloco, apartamentos in
                               apartamentos_por_bloco.items()}

    print("Blocos disponíveis:", blocos)
    print("Apartamentos por Bloco:", _apartamentos_por_bloco)

    bloco_selecionado = request.form.get('bloco')
    apartamento_selecionado = request.form.get('apartamento')

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
    blocos = db.session.query(Morador.bloco).distinct().all()
    blocos = [bloco[0] for bloco in blocos]
    apartamentos_por_bloco = {
        bloco: db.session.query(Morador.apartamento).filter_by(bloco=bloco).distinct().all()
        for bloco in blocos
    }
    apartamentos_por_bloco = {
        bloco: sorted([apt[0] for apt in db.session.query(Morador.apartamento).filter_by(bloco=bloco).distinct().all()])
        for bloco in blocos
    }

    return render_template('notificacao.html', blocos=blocos, apartamentos_por_bloco=apartamentos_por_bloco,
                           conectado=is_whatsapp_connected)


@app.route('/enviar_notificacao', methods=['POST'])
def enviar_notificacao():
    global is_whatsapp_connected
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
    _Morador = Morador.query.filter_by(bloco=bloco, apartamento=apartamento).all()
    if not _Morador:
        flash('Nenhum contato encontrado para esse apartamento.')
        return redirect(url_for('notificacao'))
    contatos_enviados = str()
    for morador in _Morador:
        print(morador.contato)
        payload = {"contato": morador.contato, "mensagem": mensagem_padrao}
        try:
            resp = requests.post('http://localhost:3000/enviar-mensagem', json=payload)
            print(resp.status_code)
            if resp.status_code == 500:
                is_whatsapp_connected = False
                return redirect(url_for('mostrar_qr'))
            elif resp.status_code == 200:
                is_whatsapp_connected = True
                morador.ultima_notificacao = datetime.now()
                morador.encomenda_pendente = True
                db.session.commit()
                flash(f"Mensagem enviada para {bloco} - {apartamento}")
                contatos_enviados += morador.contato + '\n'
            else:
                is_whatsapp_connected = False
                flash(f"Erro ao enviar mensagem: {resp.text}")
                return redirect(url_for('mostrar_qr'))
        except Exception as e:
            flash(f"Erro ao enviar mensagem: {str(e)}")
            return redirect(url_for('mostrar_qr'))
    registro = HistoricoRegistro(
        tipo="Envio",
        bloco=bloco,
        apartamento=apartamento,
        contato=contatos_enviados,
        mensagem=mensagem_padrao.split(':')[0],
        registrado_por="Sistema"
    )
    db.session.add(registro)
    db.session.commit()
    return redirect(url_for('notificacao'))


@app.route('/enviar_notificacao_em_grupo', methods=['POST'])
def enviar_notificacao_em_grupo():
    global is_whatsapp_connected
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
        moradores = Morador.query.filter_by(bloco=bloco, apartamento=apartamento).all()

        if not moradores:
            flash(f"Não há moradores cadastrados no {bloco} - {apartamento}.")
            continue

        contatos_enviados = str()
        for morador in moradores:
            payload = {"contato": morador.contato, "mensagem": mensagem_padrao}
            try:
                resp = requests.post('http://localhost:3000/enviar-mensagem', json=payload)
                if resp.status_code == 200:
                    is_whatsapp_connected = True
                    morador.ultima_notificacao = datetime.now()
                    morador.encomenda_pendente = True
                    db.session.commit()
                    contatos_enviados += morador.contato + '\n'
                    time.sleep(2)
                else:
                    is_whatsapp_connected = False
                    flash(f"Erro ao enviar mensagem para {morador.contato}: {bloco} - {apartamento}")
                    return redirect(url_for('mostrar_qr'))
            except Exception as e:
                flash(f"Erro ao enviar mensagem para {morador.contato}: {bloco} - {apartamento}")
                return redirect(url_for('mostrar_qr'))
        flash(f"Mensagem enviada para {bloco} - {apartamento}")
        registro = HistoricoRegistro(
            tipo="Envio",
            bloco=bloco,
            apartamento=apartamento,
            contato=contatos_enviados,
            mensagem=mensagem_padrao.split(':')[0],
            registrado_por="Sistema"
        )
        db.session.add(registro)
        db.session.commit()
    flash("Notificações enviadas com sucesso!")
    return redirect(url_for('notificacao'))


@app.route('/remover-encomenda/<contato>', methods=['POST'])
def remover_encomenda(contato):
    global is_whatsapp_connected
    morador = Morador.query.filter_by(contato=contato, encomenda_pendente=True).first()
    if morador:
        moradores_no_apartamento = Morador.query.filter_by(
            bloco=morador.bloco, apartamento=morador.apartamento, encomenda_pendente=True
        ).all()

        for m in moradores_no_apartamento:
            m.encomenda_pendente = False

        db.session.commit()
        registro = HistoricoRegistro(
            tipo="Retirada",
            bloco=morador.bloco,
            apartamento=morador.apartamento,
            contato=morador.contato,
            mensagem="Retirada via WhatsApp.",
            registrado_por="Usuário (WhatsApp)"
        )
        db.session.add(registro)
        db.session.commit()
        is_whatsapp_connected = True
        return jsonify(
            {"message": f"Encomenda do {morador.bloco} - {morador.apartamento} foi marcada como retirada."}), 200
    else:
        return jsonify({"error": "Nenhuma encomenda pendente encontrada para este contato."}), 404


@app.route('/remover-encomenda-porteiro/<bloco>/<apartamento>', methods=['GET', 'POST'])
def remover_encomenda_porteiro(bloco, apartamento):
    global is_whatsapp_connected
    if request.method == 'POST':
        observacao = request.form.get('observacao')
        moradores_no_apartamento = Morador.query.filter_by(bloco=bloco, apartamento=apartamento,
                                                           encomenda_pendente=True).all()

        if not moradores_no_apartamento:
            flash(f"Nenhuma encomenda pendente encontrada para o {bloco} - {apartamento}.")
            return redirect(url_for('historico_notificacoes'))

        contatos_list = str()
        for morador in moradores_no_apartamento:
            morador.encomenda_pendente = False

            mensagem = f"📦 Olá! A encomenda no {bloco} - {apartamento} foi registrada como retirada."
            try:
                resp = requests.post(
                    'http://localhost:3000/enviar-mensagem',
                    json={"contato": morador.contato, "mensagem": mensagem}
                )
                if resp.status_code == 200:
                    is_whatsapp_connected = True
                    contatos_list += morador.contato + '\n'
            except Exception as e:
                print(f"Erro ao enviar notificação para {morador.contato}: {e}")

        db.session.commit()
        registro = HistoricoRegistro(
            tipo="Retirada",
            bloco=bloco,
            apartamento=apartamento,
            contato=contatos_list.strip(),
            mensagem="Retirada pela portaria.",
            registrado_por="Porteiro",
            observacao=observacao
        )
        db.session.add(registro)
        db.session.commit()

        flash(f"A retirada foi registrada com sucesso para o {bloco} - {apartamento}.")
        return redirect(url_for('historico_notificacoes'))
    return render_template('remover_encomenda_form.html', bloco=bloco, apartamento=apartamento,
                           conectado=is_whatsapp_connected)


@app.route('/historico-envios-e-retiradas', methods=['GET', 'POST'])
def historico_envios_e_retiradas():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo = request.args.get('tipo')
    bloco = request.args.get('bloco')
    apartamento = request.args.get('apartamento')
    registrado_por = request.args.get('registrado_por')

    query = HistoricoRegistro.query

    if data_inicio:
        query = query.filter(HistoricoRegistro.data_registro >= datetime.strptime(data_inicio, '%Y-%m-%d'))
    if data_fim:
        query = query.filter(
            HistoricoRegistro.data_registro <= datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1))
    if tipo:
        query = query.filter(HistoricoRegistro.tipo == tipo)
    if bloco:
        query = query.filter(HistoricoRegistro.bloco == bloco)
    if apartamento:
        query = query.filter(HistoricoRegistro.apartamento == apartamento)
    if registrado_por:
        query = query.filter(HistoricoRegistro.registrado_por == registrado_por)
    registros = query.order_by(HistoricoRegistro.data_registro.desc()).all()
    blocos = db.session.query(HistoricoRegistro.bloco).distinct().all()
    blocos = [b[0] for b in blocos]

    apartamentos = db.session.query(HistoricoRegistro.apartamento).distinct().all()
    apartamentos = [a[0] for a in apartamentos]
    return render_template(
        'historico_registros.html',
        registros=registros,
        blocos=blocos,
        apartamentos=apartamentos,
        conectado=is_whatsapp_connected
    )


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

@app.route('/exportar-historico', methods=['GET'])
def exportar_historico():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo = request.args.get('tipo')
    bloco = request.args.get('bloco')
    apartamento = request.args.get('apartamento')
    registrado_por = request.args.get('registrado_por')
    query = HistoricoRegistro.query

    if data_inicio:
        query = query.filter(HistoricoRegistro.data_registro >= datetime.strptime(data_inicio, '%Y-%m-%d'))
    if data_fim:
        query = query.filter(HistoricoRegistro.data_registro <= datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1))
    if tipo:
        query = query.filter(HistoricoRegistro.tipo == tipo)
    if bloco:
        query = query.filter(HistoricoRegistro.bloco == bloco)
    if apartamento:
        query = query.filter(HistoricoRegistro.apartamento == apartamento)
    if registrado_por:
        query = query.filter(HistoricoRegistro.registrado_por == registrado_por)

    # Obter registros filtrados
    registros = query.order_by(HistoricoRegistro.data_registro.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_NONE, escapechar='\\')

    writer.writerow(["Data", "Tipo", "Bloco", "Apartamento", "Contato", "Mensagem", "Registrado Por", "Observação"])
    for registro in registros:
        writer.writerow([
            registro.data_registro.strftime('%d/%m/%Y %H:%M'),
            registro.tipo.replace('\n', ' ') if registro.tipo else registro.tipo,
            registro.bloco.replace('\n', ' ') if registro.bloco else registro.bloco,
            registro.apartamento.replace('\n', ' ') if registro.apartamento else registro.apartamento,
            '| ' + registro.contato.replace("\n", " | ") + ' | ' or "N/A" if registro.contato[-1] != '\n' else '| ' + registro.contato.replace("\n", " | ") or "N/A",
            registro.mensagem.replace('\n', ' ') if registro.mensagem else registro.mensagem,
            registro.registrado_por.replace('\n', ' ') if registro.registrado_por else registro.registrado_por,
            registro.observacao.replace('\n', ' ') or "N/A" if registro.observacao else "N/A"
        ])
    bom_output = "\ufeff" + output.getvalue()
    response = Response(
        bom_output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment;filename=historico_registros.csv",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )
    output.close()
    return response


# ========= Iniciar o Servidor ===========
if __name__ == '__main__':
    status_thread = threading.Thread(target=update_whatsapp_status, daemon=True)
    status_thread.start()
    app.run(debug=True)