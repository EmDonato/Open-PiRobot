---
name: ros2-humble-jazzy-migration
description: Migrare progetti ROS 2 da Humble a Jazzy con superproject Git, submodule anche annidati e container separati per modulo. Usare per inventario, piano e implementazione del porting, package Python/C++, interfacce custom, launch, parametri, dipendenze, CI e gestione dei gitlink, verificando il repository effettivamente disponibile.
---

# Migrare ROS 2 Humble a Jazzy

Rispondere in italiano salvo diversa richiesta. Distinguere audit, implementazione e verifica: eseguire soltanto lo scope richiesto. La creazione di questa skill non autorizza di per sé la migrazione di un repository.

## 1. Ispezionare il progetto

- Individuare la root e leggere le istruzioni applicabili, comprese quelle nei submodule. Cercare nel workspace corrente e chiedere il percorso solo se il repository non è reperibile.
- Considerare accertato il modello «submodule con container separati»; ricavare nomi, percorsi, versioni e topologia dal codice, senza presumere dettagli da conversazioni precedenti.
- Registrare stato e commit senza cambiare checkout:

```bash
git status --short --branch
git rev-parse HEAD
git submodule status --recursive
git config --file .gitmodules --get-regexp '^submodule\..*\.(path|branch)$'
git submodule foreach --recursive 'git status --short --branch; git rev-parse HEAD'
```

- Gestire l'assenza di `.gitmodules`. Interpretare i prefissi di submodule status: `-` non inizializzato, `+` HEAD diverso dal gitlink, `U` conflitto. Non normalizzarli automaticamente.
- Usare `rg --files --hidden` escludendo metadati Git e directory generate; ripetere nei submodule inizializzati. Leggere Dockerfile, Compose/override/profili, entrypoint, script run/build, CI, .repos, package.xml, CMake/setup, requirements, launch, YAML e plugin XML.
- Produrre una tabella: repository/percorso, SHA e branch iniziali, package, servizio/container, build context, architettura, dipendenze, contratti ROS, disponibilità Jazzy, rischio e verifica prevista.
- Distinguere dipendenze di compilazione, scambio di file e comunicazione DDS; non imporre dipendenze di build tra nodi che comunicano soltanto via topic.
- Raccogliere la baseline Humble disponibile: avvio, topic, TF, frequenze, risorse e problemi preesistenti. Segnalare ciò che non è eseguibile.

## 2. Definire target e ordine

- Assumere inizialmente container Jazzy su Ubuntu Noble 24.04, verificando tag e piattaforma. Distinguere userland del container e kernel/driver host: non richiedere automaticamente un upgrade dell'host.
- Verificare Python effettivo, toolchain e librerie native. Non imporre C++20 solo perché si passa a Jazzy.
- Leggere [references/compatibility.md](references/compatibility.md) per la matrice condizionale e le fonti ufficiali. Considerare anche i cambi introdotti in Iron; preferire la versione installata alle indicazioni Rolling.
- Classificare ogni dipendenza: binario Jazzy disponibile per l'architettura, sorgente upstream con ref verificato, patch locale necessaria oppure bloccante. Non inventare un branch `jazzy`.
- Migrare secondo le dipendenze: interfacce/librerie comuni, driver e nodi base, stima di stato, SLAM/Nav2 se presenti, bringup e integrazione.
- Conservare Humble recuperabile mediante commit e immagini identificabili. Scegliere varianti Jazzy o parametrizzazione senza duplicare inutilmente l'intero progetto.
- Applicare `$ros2-jazzy-containers` e `$ros2-jazzy-validation` se disponibili; in loro assenza svolgere comunque le fasi equivalenti.

## 3. Gestire i submodule senza perdere lavoro

- Registrare SHA del superproject, gitlink registrati e HEAD effettivi ricorsivi prima delle modifiche. Preservare file modificati/non tracciati e branch esistenti.
- Non usare reset/clean, stash automatici o `git submodule update --remote` per uniformare il checkout.
- Creare un branch di migrazione nel parent e nei soli repository modificati, controllando eventuali branch esistenti. Se un submodule è detached, creare il branch dal commit effettivo prima di modificarlo. Il branch del parent non si propaga ai figli.
- Per un submodule mancante, leggere il gitlink dal parent e inizializzare soltanto quanto necessario al commit registrato, se accessibile e autorizzato. Non aggiornare indiscriminatamente quelli già inizializzati né cambiarne URL o tracking branch.
- Per upstream di sola lettura, scegliere un fork accessibile o una patch esplicita e riproducibile nella build. Non lasciare la soluzione dipendente da modifiche locali invisibili.
- Mantenere diff separati per repository. Seguire l'autorizzazione dell'utente e le regole del progetto per commit e pubblicazione; non pubblicare automaticamente codice del robot.
- Quando si registrano commit, procedere dai figli più profondi ai parent; aggiornare i gitlink dopo i commit figli. Il parent conserva SHA, non il contenuto non committato dei submodule.
- Quando la pubblicazione è autorizzata, rendere raggiungibili i commit figli sui rispettivi remote prima di pubblicare il parent. Non consegnare gitlink verso commit disponibili soltanto localmente.
- Controllare `git diff --submodule=log` e stato ricorsivo finale. Specificare per il rollback commit, immagini, configurazioni e volumi, non soltanto un nome di branch.

## 4. Adattare il minimo necessario

- Aggiornare immagini, repository apt, dipendenze e script per il target verificato. Compilare nei container, senza installare ROS sull'host per aggirare errori.
- Correggere package.xml, rosdep, export/install CMake, setup Python e entry point sulla base delle dipendenze reali.
- Correggere API rclcpp/rclpy, lifecycle, executor, tf2 e plugin sulla base di errori riproducibili e documentazione della versione target.
- Verificare Python 3.12, estensioni native e PEP 668. Preferire apt/rosdep o venv compatibili con ROS; evitare aggiornamenti indiscriminati di pip/NumPy e `--break-system-packages`.
- Rigenerare .msg/.srv/.action e typesupport in ogni immagine interessata, con definizioni e revisioni allineate. Non copiare binari, virtualenv o install space Humble in Jazzy.
- Verificare launch, namespace, remapping, parametri dichiarati e plugin/Behavior Tree presenti. Non applicare sostituzioni globali di tipi di messaggio o nomi di plugin.
- Aggiornare i job CI pertinenti: checkout ricorsivo dei submodule, immagini Jazzy, risoluzione dipendenze e build/test nelle architetture realmente supportate. Non dichiarare verificato ARM64 dopo una sola build AMD64 o una compilazione emulata senza prova runtime.
- Preservare topic, frame, unità, frequenze, geometria, tarature e protocolli seriali salvo incompatibilità dimostrata. Separare correzioni preesistenti dal porting.
- In caso di «executor already spinning», ricostruire proprietà del nodo e chiamate a spin; correggere il ciclo di vita dell'executor, senza sopprimere eccezioni o aggiungere attese arbitrarie.

## 5. Costruire e verificare

- Separare build/install/log per distro, architettura e workspace, usando directory o volumi nuovi. Eseguire source soltanto di Jazzy e degli overlay Jazzy richiesti.
- Risolvere dipendenze rosdep per Jazzy nel container; analizzare chiavi mancanti senza nasconderle con `|| true` o skip generici.
- Eseguire build e test pertinenti per modulo, ricostruendo i consumatori dopo cambi a interfacce o librerie.
- Validare processo singolo, coppie di container e stack completo: dati reali, DDS, QoS, servizi/action, TF, clock e lifecycle.
- Non assumere interoperabilità Humble/Jazzy come architettura finale. Verificarla esplicitamente se necessaria nella transizione.
- Usare simulazione/replay quando disponibili. Verificare che il bringup non attivi attuatori; non emettere comandi motore o goal fisici senza richiesta esplicita di prova hardware.

## 6. Consegnare evidenze

Aggiornare la documentazione prevista dal progetto, oppure un unico `MIGRATION_HUMBLE_TO_JAZZY.md` se utile, con:

- inventario e SHA prima/dopo per repository, gitlink e stato dei diff;
- immagini/tag/digest osservati, architetture, versioni e dipendenze;
- motivazione delle modifiche e comandi di build/avvio effettivamente provati;
- matrice verifiche con esiti PASS, FAIL, BLOCKED o NOT RUN;
- componenti non verificati e procedura concreta di rollback.

Se mancano Docker, registri, submodule o hardware, completare il lavoro statico possibile e descrivere i blocchi. Dichiarare completato solo lo scope verificato.
