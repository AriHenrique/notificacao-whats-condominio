const express = require('express');
const venom = require('venom-bot');
const bodyParser = require('body-parser');

const app = express();
app.use(bodyParser.json());

let qrCodeData = null;
let clientInstance = null;
let isInitializing = false; // Controle para evitar múltiplas inicializações
let lastConnectionState = null; // Armazena o último estado para evitar loops de reconexão

function monitorClientConnection(client) {
    if (isInitializing) {
        return;
    }
    client.onStateChange((state) => {
        console.log('Estado do cliente mudou para:', state);
        lastConnectionState = state;

        if (state === 'CONFLICT' || state === 'UNPAIRED' || state === 'UNLAUNCHED') {
            console.log('Tentando recuperar conexão...');
            client.useHere(); // Recupera a sessão em caso de conflito
        }

        if (state === 'DISCONNECTED' && !isInitializing) {
            console.log('Cliente desconectado. Tentando reconectar...');
        }
    });

    // Verifica o estado periodicamente
    setInterval(async () => {
        if (isInitializing) {
            console.log('Inicialização em andamento. Ignorando verificação de estado.');
            return;
        }

        try {
            const state = await client.getConnectionState();
            if (state !== 'CONNECTED' && lastConnectionState !== state) {
                console.log(`Conexão perdida (estado: ${state}). Tentando reconectar...`);
            }
        } catch (error) {
            console.error('Erro ao verificar o estado da conexão:', error);
        }
    }, 30000); // Verifica a cada 30 segundos
}


function initializeVenomBot() {
    console.log('Iniciando o Venom-Bot...');

    venom
        .create(
            {
                session: 'sessionName',
                // headless: 'new',
                browserArgs: ['--no-sandbox', '--disable-setuid-sandbox'],
            },
            (base64Qr, asciiQR) => {
                qrCodeData = base64Qr;
                console.log('QR Code gerado, pronto para escaneamento!');
            },
            undefined,
            {logQR: false}
        )
        .then((client) => {
            clientInstance = client;
            console.log('WhatsApp está pronto para enviar mensagens!');
            qrCodeData = null;
            setupClientEventHandlers(client);
            monitorClientConnection(client); // Adiciona o monitoramento do cliente
        })
        .catch((error) => {
            console.error('Erro ao inicializar o Venom-Bot:', error);
            console.log('Tentando reiniciar o Venom-Bot em 15 segundos...');
            setTimeout(initializeVenomBot, 15000);
        })
        .finally(() => {
            isInitializing = false; // Libera a inicialização
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
                    if (response.status === 200) {
                        await client.sendText(message.from, "Obrigado! A encomenda foi registrada como retirada no sistema.");
                        await client.deleteChat(message.from);
                    } else {
                        const errorMsg = await response.json();
                    }
                } catch (error) {
                    console.error('Erro ao enviar solicitação ao Flask:', error);
                    await client.sendText(message.from, 'Não foi possível processar sua retirada.');
                    await client.deleteChat(message.from);
                }
            } else if (message.body.toLowerCase().startsWith("cadastrar")) {
                const regex = /cadastrar\s+(\d+)-(\d+)/i;
                const correspondencia = message.body.toLowerCase().match(regex);
                if (correspondencia) {
                    const bloco = 'Bloco ' + parseInt(correspondencia[1], 10).toString();
                    const apartamento = 'Apartamento ' + parseInt(correspondencia[2], 10).toString();
                    console.log(JSON.stringify({bloco, apartamento, contato}));

                    try {
                        const response = await fetch('http://127.0.0.1:5000/adicionar', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({bloco, apartamento, contato}),
                        });

                        if (response.ok) {
                            await client.sendText(message.from, `${bloco}, ${apartamento}\n\nCadastrado com sucesso!`);
                            await client.deleteChat(message.from);
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
                    await client.deleteChat(message.from);
                }
            } else {
                await client.sendText(message.from, "comandos aceitos: \n- cadastrar\n- retirada\n\nDigite *cadastrar* para cadastrar um morador, ou *retirada* para informar que a encomenda foi retirada.");
                await client.deleteChat(message.from);
            }
        } catch (error) {
            console.error(`Erro no processamento da mensagem: ${message.from}`, error);
        }
    });
}

async function enviarComTimeout(clientInstance, contato, mensagem, timeoutMs = 15000) {
    await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
            reject(new Error('Timeout no envio da mensagem.'));
        }, timeoutMs);

        clientInstance.sendText(`55${contato}@c.us`, mensagem)
            .then((result) => {
                clearTimeout(timeout);
                resolve(result);
            })
            .catch((error) => {
                clearTimeout(timeout);
                reject(error);
            });
    });
    await clientInstance.deleteChat(`55${contato}@c.us`);
}

initializeVenomBot();

app.get('/health', async (req, res) => {
    if (!clientInstance) {
        return res.status(500).json({status: 'error', message: 'Cliente não inicializado.'});
    }

    try {
        const state = await clientInstance.getConnectionState();
        const isConnected = state === 'CONNECTED';

        if (!isConnected) {
            console.log('Cliente desconectado. Tentando reconectar...');
        }

        res.status(200).json({
            status: 'success',
            clientState: state,
            isConnected,
            message: isConnected
                ? 'O cliente está conectado e funcionando normalmente.'
                : 'O cliente não está conectado. Tentando reconectar.',
        });
    } catch (error) {
        console.error('Erro ao verificar o estado do cliente:', error);
        res.status(500).json({status: 'error', message: 'Erro ao verificar o estado do cliente.'});
    }
});


app.get('/qr-code', (req, res) => {
    if (qrCodeData) {
        res.send(`<img src="${qrCodeData}" style="width:300px;height:300px;" />`);
    } else {
        res.send('Nenhum QR Code disponível no momento.');
    }
});


app.post('/enviar-mensagem', async (req, res) => {
    const {contato, mensagem} = req.body;
    if (!contato || !mensagem) {
        return res.status(400).send('Faltam informações.');
    }

    if (!clientInstance) {
        return res.status(500).send('Cliente não está inicializado.');
    }

    try {
        await enviarComTimeout(clientInstance, contato, mensagem, 15000);
        res.status(200).send(`Mensagem enviada para ${contato}`);


    } catch (error) {
        console.error(`[ERRO] Falha ao enviar mensagem para ${contato}: ${error}`);
        res.status(500).send('Erro ao enviar mensagem: ' + error);
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
