---
name: ros2-jazzy-containers
description: Adattare e diagnosticare Dockerfile, Compose, entrypoint, immagini e networking DDS per migrare ROS 2 Humble a Jazzy in progetti multi-container con submodule Git. Usare per isolamento delle build, dipendenze Python e ABI, architetture, mount, dispositivi, discovery e riproducibilità.
---

# Adattare i container ROS 2 a Jazzy

Operare sui container reali, rispettando istruzioni del repository e modifiche locali. Conservare l'architettura per modulo; non migrare altri submodule senza necessità.

## Ispezionare la configurazione effettiva

1. Individuare Dockerfile multi-stage, basi interne/vendor, build args, Compose/override/profili, .env, entrypoint, script run/build e CI.
2. Identificare i file effettivamente usati e la CLI disponibile (`docker compose` oppure `docker-compose`); non imporre un aggiornamento del motore per una differenza di sintassi.
3. Espandere la configurazione effettiva, usando `config --quiet` se supportato. Se si legge il rendering completo, non riportare segreti o credenziali.
4. Mappare per servizio: repository, build context, Dockerfile/target, immagini parent, architettura, workspace, entrypoint/command, mount, rete, IPC, device e dipendenze.
5. Verificare init dei submodule al ref previsto, .dockerignore, symlink esterni al build context e file dell'immagine nascosti da bind mount.

## Preparare immagini e dipendenze

- Scegliere una base Jazzy/Noble appropriata e verificarne tag/manifest sulle architetture richieste. Non presumere che un'immagine desktop o vendor esista per ARM64.
- Distinguere userland container e kernel/driver host. Non richiedere automaticamente Ubuntu sull'host di un container Ubuntu.
- Per CUDA, Jetson, Hailo o altre basi vendor verificare driver/runtime/SDK prima di sostituire la base; dichiarare un blocco se manca una combinazione supportabile.
- Separare il porting della distro dagli aggiornamenti opzionali. Verificare pacchetti binari e ref sorgente per piattaforma; non presumere un branch Jazzy upstream.
- Aggiornare fonti apt, codename e setup ROS secondo istruzioni ufficiali Jazzy correnti. Non usare repository Jammy in Noble.
- Usare apt/rosdep dentro l'immagine, gestendo realmente gli errori; non ignorarli con `|| true` o skip generici.
- Verificare Python 3.12, PEP 668, wheel native, OpenCV/NumPy e SDK. Se serve un venv, usare un interprete compatibile con ROS e verificare import e shebang; valutare `--system-site-packages` per i package ROS di sistema.
- Ricompilare estensioni native e typesupport custom. Conservare lo standard C++ se compatibile.
- Distinguere tag Humble/Jazzy; registrare digest e versioni osservati. Non promettere riproducibilità esatta con dipendenze apt/pip non fissate.

## Isolare build e runtime

- Separare build/install/log e cache CMake per distro, architettura e workspace; non cancellare gli artefatti Humble.
- Non montare /opt/ros, virtualenv o librerie di sistema dell'host per risolvere dipendenze nel container.
- Verificare che i mount non nascondano l'install compilato nell'immagine e che sviluppo/produzione usino layout coerenti.
- Ricordare che il source in un layer RUN non persiste nel successivo e che la shell predefinita può essere /bin/sh; usare Bash esplicito dove necessario.
- Nell'entrypoint eseguire source di Jazzy e degli overlay richiesti; fallire se manca un overlay obbligatorio, poi usare `exec "$@"` per inoltrare i segnali.
- Preservare UID/GID e permessi dei volumi. Verificare stop/uscita/riavvio e gestione dei processi, senza aggiungere background non supervisionati.
- Isolare il progetto Compose di prova. Controllare anche container_name, porte pubblicate, volumi e reti external: il solo parametro -p non isola tutto.
- Verificare profili e depends_on; l'ordine di creazione non prova la disponibilità di un nodo ROS. Aggiungere readiness pertinente solo dove serve.

## Verificare rete DDS e dispositivi

- Controllare nei processi ROS_DOMAIN_ID, RMW_IMPLEMENTATION, pacchetto RMW, ROS_LOCALHOST_ONLY, discovery e XML vendor. Preservare le scelte esistenti finché non emerge una causa concreta.
- Usare inizialmente un RMW coerente per ridurre variabili, senza dichiararlo requisito universale di interoperabilità DDS.
- Verificare interfacce, multicast/unicast, routing, subnet, firewall/VPN e dimensioni dei messaggi. Il port mapping non risolve in generale il discovery DDS.
- Valutare network_mode host solo quando appropriato alla piattaforma; distinguere Linux, Docker Desktop e WSL, evitando cambi indiscriminati.
- Per problemi shared memory verificare namespace IPC, /dev/shm, permessi e profilo vendor; provare un trasporto alternativo mirato. Non imporre ipc host come soluzione universale.
- Dopo cambi di RMW/dominio controllare il daemon ROS CLI nel medesimo ambiente e riavviarlo se necessario; distinguere cache CLI e traffico reale.
- Preservare solo gli accessi necessari a USB/seriale, gruppi, regole udev host, hotplug e acceleratori. Non introdurre privileged true per aggirare un errore non diagnosticato.
- Separare dominio di test e operativo; l'isolamento DDS non isola device fisici, file o porte.
- Non assumere interoperabilità Humble/Jazzy; se richiesta nella transizione verificarla con tipi, QoS, RMW, servizi/action reali.

## Verificare e consegnare

1. Validare sintassi Compose e script con strumenti disponibili.
2. Costruire le basi prima dei servizi dipendenti; ricorrere a --no-cache solo per cache sospetta o verifica pulita motivata.
3. Avviare i servizi isolati, verificare distro, import e interfacce custom, poi dati tra due container e contratti applicativi.
4. Controllare shutdown, restart loop, overlay misti, mount Humble e librerie della piattaforma sbagliata.
5. Riportare configurazione effettiva, immagini/versioni, modifiche, comandi provati, risultati e rollback. Distinguere verifiche statiche da build/runtime non eseguiti.

Controllare che gli avvii di prova non abilitino attuatori; non emettere comandi motore o avviare prove fisiche come parte implicita di una verifica Docker.
