from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path
import requests
import time
import os
import signal
import psutil
import threading


app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///Morador.db'
db = SQLAlchemy(app)
is_whatsapp_connected = False

# Modelo de dados atualizado (sem o campo 'nome')
class Morador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bloco = db.Column(db.String(50), nullable=False)
    apartamento = db.Column(db.String(50), nullable=False)
    contato = db.Column(db.String(100), nullable=False)

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


# ========= Rota para Cadastro ===========
@app.route('/cadastro')
def cadastro():
    blocos_predefinidos = [f'Bloco {i}' for i in range(1, 10)]
    apartamentos_predefinidos = [f"Apartamento {i}0{j}" for i in range(1, 6) for j in range(1, 5)]
    return render_template('cadastro.html', blocos=blocos_predefinidos, apartamentos=apartamentos_predefinidos, conectado=is_whatsapp_connected)

@app.route('/adicionar', methods=['POST'])
def adicionar_morador():
    if request.is_json:
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
        if request.is_json:  # Adicionar morador enviado via JSON
            novo_morador = Morador(bloco=bloco, apartamento=apartamento, contato=contato)
            db.session.add(novo_morador)
        else:  # Adicionar moradores enviados pelo formulário
            for contato in contatos:
                print(f"contato: {contato}")
                novo_morador = Morador(bloco=bloco, apartamento=apartamento, contato=contato)
                db.session.add(novo_morador)
        db.session.commit()
        flash('Morador cadastrado com sucesso!')
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
    blocos_predefinidos = [f'Bloco {i}' for i in range(1, 10)]
    apartamentos_predefinidos = [f"Apartamento {i}0{j}" for i in range(1, 6) for j in range(1, 5)]

    if request.method == 'POST':
        bloco = request.form.get('bloco')
        apartamento = request.form.get('apartamento')

        # Remover todos os contatos relacionados
        db.session.query(Morador).filter_by(bloco=bloco, apartamento=apartamento).delete()
        db.session.commit()
        flash(f'Todos os contatos do {bloco} - {apartamento} foram removidos com sucesso.')
        return redirect(url_for('remover_morador'))

    return render_template('remover.html', blocos=blocos_predefinidos, apartamentos=apartamentos_predefinidos,conectado=is_whatsapp_connected)

# ========= Rota para Modificar Contatos ===========
@app.route('/modificar', methods=['GET', 'POST'])
def modificar_contatos():
    blocos_predefinidos = [f'Bloco {i}' for i in range(1, 10)]
    apartamentos_predefinidos = [f"Apartamento {i}0{j}" for i in range(1, 6) for j in range(1, 5)]

    bloco_selecionado = request.form.get('bloco')
    apartamento_selecionado = request.form.get('apartamento')
    print(f"bloco_selecionado: {bloco_selecionado}")
    print(f"apartamento_selecionado: {apartamento_selecionado}")
    _Morador = []
    if request.method == 'POST':
        _Morador = Morador.query.filter_by(bloco=bloco_selecionado, apartamento=apartamento_selecionado).all()
        print(_Morador)
    return render_template(
        'modificar.html',
        blocos=blocos_predefinidos,
        apartamentos=apartamentos_predefinidos,
        Morador=_Morador,
        bloco_selecionado=bloco_selecionado,
        apartamento_selecionado=apartamento_selecionado,
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
    blocos_predefinidos = [f'Bloco {i}' for i in range(1, 10)]
    apartamentos_predefinidos = [f"Apartamento {i}0{j}" for i in range(1, 6) for j in range(1, 5)]
    return render_template('notificacao.html', blocos=blocos_predefinidos, apartamentos=apartamentos_predefinidos, conectado=is_whatsapp_connected)

@app.route('/enviar_notificacao', methods=['POST'])
def enviar_notificacao():
    bloco = request.form.get('bloco')
    apartamento = request.form.get('apartamento')
    mensagem_padrao = f"""📦 *Atenção, morador! {bloco} - {apartamento}*
Há encomendas disponíveis para retirada na portaria. 
Por favor, compareça para a retirada o mais breve possível.
    
Obrigado pela colaboração!
_Portaria_"""

    # Buscar contatos relacionados
    _Morador = Morador.query.filter_by(bloco=bloco, apartamento=apartamento).all()
    if not Morador:
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
                flash(f"Mensagem enviada para {bloco} - {apartamento}")
            else:
                flash(f"Erro ao enviar mensagem: {resp.text}")
        except Exception as e:
            flash(f"Erro ao enviar mensagem: {str(e)}")
            return redirect(url_for('mostrar_qr'))
    return redirect(url_for('notificacao'))

@app.route('/fechar')
def fechar_sistema():
    try:
        import requests
        requests.get('http://localhost:3000/encerrar')
        current_pid = os.getpid()
        parent = psutil.Process(current_pid)
        for child in parent.children(recursive=True):
            child.terminate()
        parent.terminate()
        flash('Sistema encerrado com sucesso.')
    except Exception as e:
        flash(f'Erro ao encerrar o sistema: {str(e)}')
    return redirect(url_for('index'))


# ========= Iniciar o Servidor ===========
if __name__ == '__main__':
    caminho_pasta = Path("C:/NotificacaoEncomenda/back/tokens")
    if caminho_pasta.exists() and caminho_pasta.is_dir():
        status_thread = threading.Thread(target=update_whatsapp_status, daemon=True)
        status_thread.start()
    app.run(debug=True)
