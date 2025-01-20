!define APP_NAME "NotificacaoEncomenda"
!define INSTALL_DIR "C:\NotificacaoEncomenda"

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

    ; Copiar o Back-End (Node.js)
    DetailPrint "Copiando arquivos do Back-End..."
    SetOutPath "${INSTALL_DIR}\back"
    File /r "back\*"

    ; Copiar o Front-End (Flask)
    DetailPrint "Copiando arquivos do Front-End..."
    SetOutPath "${INSTALL_DIR}\front"
    File /r "front\*"

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
