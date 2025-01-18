!define APP_NAME "NotificacaoEncomenda"
!define INSTALL_DIR "C:\NotificacaoEncomenda"
!define NODE_VERSION "18.16.0"
!define PYTHON_VERSION "3.10.9"
!define NODE_URL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-x64.msi"
!define PYTHON_URL "https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe"

Outfile "setup-${APP_NAME}.exe"
InstallDir "${INSTALL_DIR}"
RequestExecutionLevel admin

Section "Instalar Aplicação"

    ; Remover a pasta de instalação, se ela já existir
    IfFileExists "${INSTALL_DIR}\*.*" 0 +2
    RMDir /r "${INSTALL_DIR}"

    ; Criar o diretório principal
    DetailPrint "Criando diretório de instalação..."
    CreateDirectory "${INSTALL_DIR}"

    ; Configurar o Back-End (Node.js)
    DetailPrint "Baixando e instalando Node.js..."
    SetOutPath "$TEMP"
    ExecWait 'curl -o node-installer.msi ${NODE_URL}'
    ExecWait 'msiexec /i node-installer.msi /passive /norestart'

    DetailPrint "Configurando o Back-End..."
    SetOutPath "${INSTALL_DIR}\back"
    File /r "back\*"
    ExecWait 'cmd.exe /C "cd ${INSTALL_DIR}\back && npm install"'

    ; Configurar o Front-End (Flask)
    DetailPrint "Baixando e instalando Python..."
    ExecWait 'curl -o python-installer.exe ${PYTHON_URL}'
    ExecWait 'python-installer.exe /passive InstallAllUsers=1 PrependPath=1'

    DetailPrint "Configurando o Front-End..."
    SetOutPath "${INSTALL_DIR}\front"
    File /r "front\*"
    ExecWait 'cmd.exe /C "cd ${INSTALL_DIR}\front && python -m venv venv && venv\Scripts\pip install -r requirements.txt"'

    ; Voltar ao diretório raiz para copiar os arquivos de inicialização
    SetOutPath "${INSTALL_DIR}"
    DetailPrint "Copiando arquivos de inicialização..."
    File "start_silent.bat"
    File "start.vbs"

    ; Copiar o ícone para o diretório raiz
    DetailPrint "Copiando ícone..."
    File /oname=${INSTALL_DIR}\notification.ico "front\bot\static\notification.ico"

    ; Criar atalhos no desktop com ícone personalizado
    DetailPrint "Criando atalho na área de trabalho com ícone..."
    CreateShortCut "$DESKTOP\Iniciar ${APP_NAME}.lnk" "${INSTALL_DIR}\start.vbs" "" "${INSTALL_DIR}\notification.ico"

SectionEnd

Section -Post
    ; Exibir mensagem ao finalizar
    MessageBox MB_ICONINFORMATION|MB_OK "${APP_NAME} foi instalado com sucesso!"
SectionEnd
