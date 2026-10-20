---
name: ros2-jazzy-validation
description: Verificare e diagnosticare migrazioni ROS 2 Humble a Jazzy con submodule e container separati. Usare per build/test nel container, contratti topic-servizi-action, QoS, TF, clock, lifecycle, driver, Nav2/SLAM se presenti, regressioni e report con evidenze e limiti di copertura.
---

# Verificare una migrazione ROS 2 Jazzy

Leggere istruzioni e inventario del progetto; ricavare package, servizi, workspace, topic e frame dai file reali. Usare la baseline Humble disponibile. Non assumere che tutti i componenti elencati siano presenti.

## Preparare la verifica

- Registrare SHA del parent e submodule, immagini/tag/digest osservati, architettura, OS, Python, package ROS, RMW e file/profili Compose.
- Preparare una matrice: modulo, verifica, comando effettivo, ambiente, atteso, osservato e stato PASS, FAIL, BLOCKED o NOT RUN.
- Distinguere hardware reale, simulazione e replay: un rosbag non prova accesso USB o correttezza di un driver fisico.
- Derivare soglie di frequenza, latenza e risorse da requisiti/baseline; non inventare valori universali.
- Usare dominio ROS, progetto Compose e output dedicati, controllando conflitti di porte, nomi espliciti, volumi e device. Non interrompere lo stack operativo per ottenere un ambiente pulito.
- Prima di avviare un servizio controllare se collega attuatori o genera movimenti automatici; usare mock/replay o modalità con attuatori esplicitamente disabilitati. Eseguire prove fisiche soltanto se richieste.

## Livello 1: struttura e build

1. Controllare stato Git ricorsivo, gitlink, submodule mancanti e diff. Per una consegna, verificare che i commit referenziati siano raggiungibili da chi ricostruisce.
2. Validare Compose, script, percorsi, build context, dipendenze tra immagini e init dei submodule.
3. Verificare distro Jazzy, overlay, Python, ABI e dipendenze dentro ogni container; provare import di rclpy e interfacce custom dove usati.
4. Compilare in directory nuove e usare test esistenti pertinenti. Adattare ai percorsi reali:

```bash
source /opt/ros/jazzy/setup.bash
rosdep check --from-paths src --ignore-src --rosdistro jazzy
colcon list
colcon --log-base log_jazzy build --build-base build_jazzy --install-base install_jazzy
source install_jazzy/setup.bash
colcon --log-base log_jazzy test --build-base build_jazzy --install-base install_jazzy
colcon test-result --test-result-base build_jazzy --verbose
```

5. Non occultare errori con || true. Verificare che i test non aprano hardware senza controllo.
6. Aggiungere test solo per contratti o regressioni concreti, non per controllare sostituzioni testuali di humble con jazzy.

## Livello 2: processi e lifecycle

- Controllare log, exit code, restart loop, eccezioni, caricamento librerie/plugin e stato dei nodi.
- Verificare nomi/namespace, parametri effettivi, remapping, overlay e disponibilità degli endpoint.
- Verificare transizioni lifecycle quando previste: una shell viva o un container running non dimostrano readiness.
- Provare shutdown e riavvio dei servizi di test, controllando processi orfani e rilascio delle risorse.

## Livello 3: contratti tra container

- Provare una coppia minima di nodi Jazzy su due container nella rete prevista, poi i collegamenti applicativi. Verificare dati ricevuti, non soltanto discovery.
- Controllare nome/tipo completo, definizioni custom, publisher/subscriber e QoS: reliability, durability, history/depth e ulteriori requisiti realmente usati.
- Usare node info, topic info --verbose, interface show, echo/hz/bw con QoS compatibile; controllare la sintassi disponibile con --help.
- Applicare timeout ai campionamenti. Distinguere timeout intenzionale dopo la raccolta dati da un fallimento; conservare output, durata e criterio.
- Considerare costo e QoS dei subscriber diagnostici; limitare echo/hz/bw soprattutto per video/depth per non introdurre artificialmente il problema misurato.
- Per servizi/action verificare request/response e feedback/result/cancel con richieste non attuative. Il discovery non prova la funzionalità.
- Per mancata comunicazione distinguere: nodo attivo, nome/tipo, RMW/dominio, discovery/rete, QoS, revisione interfacce e trasporto dati. Confrontare comunicazione locale e inter-container.
- Usare la CLI nel medesimo ambiente del nodo; controllare eventuale daemon rimasto con RMW/dominio precedenti.

## Livello 4: comportamento robotico

| Componente presente | Verifica |
| --- | --- |
| TF/URDF | Catena, timestamp, autorità unica per trasformazione, frame statici disponibili ai subscriber tardivi. |
| Clock | use_sim_time coerente, /clock se richiesto, sincronizzazione tra host, tempo bag/reale non mescolato. |
| LiDAR/IMU/odom | Tipi, frame, unità, segni, frequenze, covarianze e timestamp contro baseline; tarature preservate. |
| RGB-D | Encoding, dimensioni, camera_info, allineamento/sincronizzazione, CPU/RAM/banda. |
| EKF/localizzazione | Input e frame, frequenza output, autorità odom-base, warning e divergenza contro baseline. |
| SLAM | Input, TF, mappa e salvataggio/ripristino se previsto; originali preservati nel replay. |
| Nav2/costmap | Lifecycle, plugin, mappe, TF, sensori, catena velocità; goal/cancel solo in contesto autorizzato. |
| STM32/seriale | Accesso e lettura se consentiti, protocollo/watchdog preservati; nessuna scrittura attuativa implicita. |
| SDK/acceleratori | Device e librerie corrispondenti alla piattaforma; import e prova rappresentativa senza carichi arbitrari. |

Verificare Twist/TwistStamped lungo teleop, mux, controller, smoother, collision monitor e driver effettivamente presenti. Non attribuire a Jazzy i default di Kilted/Rolling; leggere codice e configurazione installati.

Prima del replay controllare doppie pubblicazioni di /tf, /clock, odometria e comandi di velocità. Non avviare due autorità della stessa trasformazione.

## Riportare il risultato

- Distinguere regressioni Jazzy e problemi Humble preesistenti; collegare ogni correzione all'evidenza.
- Classificare i fallimenti: container/infrastruttura, dipendenze/build, API/codice, interfacce/QoS, rete/clock/TF o algoritmo/configurazione.
- Riportare scope, comandi, esiti, log utili, risorse e verifiche mancanti; escludere segreti di ambiente/Compose.
- Concludere con «verificato per lo scope indicato», «implementato con verifiche bloccate» oppure «migrazione incompleta», indicando blocchi concreti.
- Dopo correzioni ripetere le verifiche interessate e dei contratti dipendenti, senza ripetere indiscriminatamente controlli già superati.
