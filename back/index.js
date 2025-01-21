const express = require('express');
const venom = require('venom-bot');
const bodyParser = require('body-parser');

const app = express();
app.use(bodyParser.json());

let qrCodeData = null;
let clientInstance = null;

function initializeVenomBot() {
    console.log('Iniciando o Venom-Bot...');
    venom
        .create(
            {
                session: 'sessionName',
                headless: 'new', // Utilize 'new' para o novo modo headless ou false para modo não headless
                browserArgs: ['--no-sandbox', '--disable-setuid-sandbox'],
            },
            (base64Qr, asciiQR) => {
                qrCodeData = base64Qr;
                console.log('QR Code gerado, pronto para escaneamento!');
            },
            undefined,
            { logQR: false }
        )
        .then((client) => {
            clientInstance = client;
            console.log('WhatsApp está pronto para enviar mensagens!');
            qrCodeData = null
            setupClientEventHandlers(client);
        })
        .catch((error) => {
            console.error('Erro ao inicializar o Venom-Bot:', error);
            console.log('Tentando reiniciar o Venom-Bot em 5 segundos...');
            setTimeout(initializeVenomBot, 5000);
        });
}

function setupClientEventHandlers(client) {
    client.onStateChange((state) => {
        console.log('Estado do cliente:', state);
        if (state === 'CONFLICT' || state === 'UNPAIRED' || state === 'UNLAUNCHED') {
            client.useHere();
        }
    });

    client.onMessage(async (message) => {
        try {
            const _contato = message.from.replace('@c.us', '').replace('55', '');
            const regex9 = /^(\d{2})(\d+)$/;
            const match = _contato.match(regex9);
            const ddd = match[1];
            const numero = match[2];
            const contato = `${ddd}9${numero}`;

            // Caso o morador envie "retirada"
            if (message.body.toLowerCase().trim() === "retirada") {
                try {
                    const response = await fetch(`http://127.0.0.1:5000/remover-encomenda/${contato}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                    });

                    if (response.ok) {
                        await client.sendText(message.from, "Obrigado! A encomenda foi registrada como retirada no sistema.");
                    } else {
                        const errorMsg = await response.json();
                        await client.sendText(message.from, `${errorMsg.error || 'Erro desconhecido.'}`);
                    }
                } catch (error) {
                    console.error('Erro ao enviar solicitação ao Flask:', error);
                    await client.sendText(message.from, 'Não foi possível processar sua retirada.');
                }
            }
            // Caso o morador envie "cadastrar"
            else if (message.body.toLowerCase().startsWith("cadastrar")) {
                const regex = /cadastrar\s+(\d+)-(\d+)/i;
                const correspondencia = message.body.toLowerCase().match(regex);
                if (correspondencia) {
                    const bloco = 'Bloco ' + correspondencia[1];
                    const apartamento = 'Apartamento ' + correspondencia[2];
                    console.log(JSON.stringify({ bloco, apartamento, contato }));

                    try {
                        const response = await fetch('http://127.0.0.1:5000/adicionar', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ bloco, apartamento, contato }),
                        });

                        if (response.ok) {
                            await client.sendText(message.from, `${bloco}, ${apartamento}\n\nCadastrado com sucesso!`);
                        } else {
                            const errorMsg = await response.json();
                        }
                    } catch (error) {
                        console.error('Erro ao enviar solicitação ao Flask:', error);
                    }
                } else {
                    await client.sendText(
                        message.from,
                        `📋 *Cadastro de Morador*
Para se cadastrar, digite a palavra *cadastrar* seguida do número do bloco e apartamento, separados por um traço. 
🔹 *Exemplo*: 
Digite: *cadastrar 1-101*`
                    );
                }
            }
            else {
                await client.sendText(message.from, "comandos aceitos: \n- cadastrar\n- retirada\n\nDigite *cadastrar* para cadastrar um morador, ou *retirada* para informar que a encomenda foi retirada.");
            }
        } catch (error) {
            console.error(`Erro no processamento da mensagem: ${message.from}`, error);
        }
    });
}

// Iniciar o Venom-Bot
initializeVenomBot();

app.get('/qr-code', (req, res) => {
    if (qrCodeData) {
        res.send(`<img src="${qrCodeData}" style="width:300px;height:300px;" />`);
    } else {
        res.send('Nenhum QR Code disponível no momento.');
    }
});

app.post('/enviar-mensagem', async (req, res) => {
    const { contato, mensagem } = req.body;

    if (!contato || !mensagem) {
        return res.status(400).send('Faltam informações.');
    }

    if (!clientInstance) {
        return res.status(500).send('Cliente não está inicializado.');
    }

    try {
        await clientInstance.sendText(`55${contato}@c.us`, mensagem);
        res.status(200).send(`Mensagem enviada para ${contato}`);
    } catch (error) {
        res.status(500).send('Erro ao enviar mensagem: ' + error.message);
    }
});

app.get('/encerrar', (req, res) => {
    console.log('Encerrando o servidor Node.js...');
    res.send('Servidor Node.js encerrado.');
    process.exit(0);
});


const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Servidor rodando em http://localhost:${PORT}`);
});

process.on('uncaughtException', (error) => {
    console.error('Erro não tratado:', error);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Rejeição não tratada:', reason);
});

process.stdin.resume();
