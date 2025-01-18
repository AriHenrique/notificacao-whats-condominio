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
            setTimeout(initializeVenomBot, 5000); // Rechama a função após 5 segundos
        });
}

function setupClientEventHandlers(client) {
    client.onStateChange((state) => {
        console.log('Estado do cliente:', state);
        if (state === 'CONFLICT' || state === 'UNPAIRED' || state === 'UNLAUNCHED') {
            client.useHere();
        }
    });

    client.onMessage((message) => {
        if (message.body === '!Ari' && message.isGroupMsg === false) {
            client
                .sendText(message.from, 'Welcome Venom 🕷')
                .then((result) => {
                    console.log('Result: ', result);
                })
                .catch((erro) => {
                    console.error('Erro ao enviar mensagem: ', erro);
                });
            console.log('Mensagem recebida:', message.body);
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
    process.exit(0); // Finaliza o processo Node.js
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

process.stdin.resume(); // Mantém o processo ativo indefinidamente
