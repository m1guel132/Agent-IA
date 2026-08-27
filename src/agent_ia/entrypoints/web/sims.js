/**
 * THE SIMS FOR AI AGENTS — 3D ISOMETRIC VIRTUAL OFFICE ENGINE
 * Built with Three.js, WebGL & Live Agent Telemetry
 */

let scene, camera, renderer, controls;
let container = document.getElementById('canvas-container');
let labelsLayer = document.getElementById('labels-layer');

// Telemetry State
let selectedAgentKey = 'hermes';
let isAutoRoam = false;
let isDarkMode = false;
let startTime = Date.now();
let tokenCounter = 12840;

// Collections of 3D objects
const agents = {};
const stations = {};
const stationLabels = [];

// Agent Definitions
const AGENT_CONFIGS = {
    hermes: {
        name: 'Hermes (Orquestador)',
        badge: 'blue-agent (Hermes)',
        color: 0x3b82f6,
        accentCss: '#3b82f6',
        task: 'Semantic Intent Routing & State Machine',
        feature: 'Hexagonal Dispatcher & Guardrails',
        station: 'desk',
        position: { x: -3.5, y: 0.7, z: 2.2 },
        targetPos: { x: -3.5, y: 0.7, z: 2.2 }
    },
    curador: {
        name: 'AgenteCurador (Archiver)',
        badge: 'orange-agent (Curador)',
        color: 0xf97316,
        accentCss: '#f97316',
        task: 'Deduplicate ChromaDB & Sync Vault',
        feature: 'Notion 29 DBs & Obsidian Markdown',
        station: 'vault',
        position: { x: -4.5, y: 0.7, z: -3.0 },
        targetPos: { x: -4.5, y: 0.7, z: -3.0 }
    },
    plan: {
        name: 'AgentePlan (Strategist)',
        badge: 'purple-agent (Plan)',
        color: 0x8b5cf6,
        accentCss: '#8b5cf6',
        task: 'Cascade Objectives -> Projects -> Tasks',
        feature: 'Relational Fast-Path Notion Planner',
        station: 'kanban',
        position: { x: 1.5, y: 0.7, z: -3.5 },
        targetPos: { x: 1.5, y: 0.7, z: -3.5 }
    },
    estudio: {
        name: 'AgenteEstudio (Scholar)',
        badge: 'green-agent (Estudio)',
        color: 0x10b981,
        accentCss: '#10b981',
        task: 'SuperMemo SM-2 Active Recall Session',
        feature: 'Flashcards Synthesis & Cornell Notes',
        station: 'study',
        position: { x: 4.8, y: 0.7, z: -1.0 },
        targetPos: { x: 4.8, y: 0.7, z: -1.0 }
    },
    sync: {
        name: 'AgenteSync (Gatekeeper)',
        badge: 'yellow-agent (Sync)',
        color: 0xf59e0b,
        accentCss: '#f59e0b',
        task: 'DataMasker Sanitization & API Filter',
        feature: 'Token & PII Local Masking Gateway',
        station: 'gate',
        position: { x: 3.0, y: 0.7, z: 3.0 },
        targetPos: { x: 3.0, y: 0.7, z: 3.0 }
    }
};

// --- INITIALIZE THREE.JS SCENE ---
function init() {
    // 1. Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xeef2f6);
    scene.fog = new THREE.FogExp2(0xeef2f6, 0.025);

    // 2. Camera (Isometric Perspective)
    const aspect = window.innerWidth / window.innerHeight;
    camera = new THREE.PerspectiveCamera(38, aspect, 0.1, 1000);
    camera.position.set(16, 15, 18);
    camera.lookAt(0, 0, 0);

    // 3. Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    // 4. Orbit Controls
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2.15; // Don't allow camera below floor
    controls.minDistance = 6;
    controls.maxDistance = 45;
    controls.target.set(0, 0.5, 0);

    // 5. Lighting
    setupLighting();

    // 6. Build World Architecture & Stations
    buildOfficeFloor();
    buildStationDesk();
    buildStationVault();
    buildStationKanban();
    buildStationStudy();
    buildStationSecurityGate();

    // 7. Spawn Agent Avatars
    spawnAllAgents();

    // 8. Event Listeners
    window.addEventListener('resize', onWindowResize);
    renderer.domElement.addEventListener('pointerdown', onCanvasClick);

    // 9. Start Loop
    animate();
    startTelemetryTicker();
}

// --- LIGHTING SETUP ---
let dirLight, ambientLight;
function setupLighting() {
    ambientLight = new THREE.AmbientLight(0xffffff, 0.75);
    scene.add(ambientLight);

    dirLight = new THREE.DirectionalLight(0xffffff, 0.85);
    dirLight.position.set(20, 30, 20);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    dirLight.shadow.camera.near = 0.5;
    dirLight.shadow.camera.far = 60;
    const d = 16;
    dirLight.shadow.camera.left = -d;
    dirLight.shadow.camera.right = d;
    dirLight.shadow.camera.top = d;
    dirLight.shadow.camera.bottom = -d;
    dirLight.shadow.bias = -0.0005;
    scene.add(dirLight);

    // Subtle colored pointlights for cyberpunk realism
    addStationPointLight(-3.5, 2, 2, 0x3b82f6, 1.2); // Desk (Blue)
    addStationPointLight(-4.5, 2, -3, 0xf97316, 1.2); // Vault (Orange)
    addStationPointLight(1.5, 2, -3.5, 0x8b5cf6, 1.2); // Kanban (Purple)
    addStationPointLight(4.8, 2, -1, 0x10b981, 1.2); // Study (Green)
    addStationPointLight(3.0, 2, 3, 0xf59e0b, 1.2); // Gate (Yellow)
}

function addStationPointLight(x, y, z, color, intensity) {
    const pl = new THREE.PointLight(color, intensity, 8);
    pl.position.set(x, y, z);
    scene.add(pl);
}

// --- ARCHITECTURAL OFFICE ENVIRONMENT ---
function buildOfficeFloor() {
    // Main Glossy Tiled Studio Floor
    const floorGeo = new THREE.PlaneGeometry(24, 24);
    const floorMat = new THREE.MeshStandardMaterial({
        color: 0xf3f5f8,
        roughness: 0.25,
        metalness: 0.15
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    // Subtle Grid Overlay
    const grid = new THREE.GridHelper(24, 24, 0xd0d7e2, 0xe2e8f0);
    grid.position.y = 0.01;
    scene.add(grid);

    // Low Modern Studio Perimeter Baseboards & Frosted Glass Walls
    const wallMat = new THREE.MeshPhysicalMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.45,
        roughness: 0.1,
        transmission: 0.6,
        thickness: 0.5
    });

    const backWall1 = new THREE.Mesh(new THREE.BoxGeometry(24, 4, 0.4), wallMat);
    backWall1.position.set(0, 2, -12);
    scene.add(backWall1);

    const backWall2 = new THREE.Mesh(new THREE.BoxGeometry(0.4, 4, 24), wallMat);
    backWall2.position.set(-12, 2, 0);
    scene.add(backWall2);
}

// --- STATION 1: DESK 01 (ACTIVE COMPUTE / HERMES) ---
function buildStationDesk() {
    const group = new THREE.Group();
    group.position.set(-3.5, 0, 1.8);

    // Modern Executive Desk (Wood + Metal Trim)
    const deskTopMat = new THREE.MeshStandardMaterial({ color: 0xc49b71, roughness: 0.4 });
    const deskTop = new THREE.Mesh(new THREE.BoxGeometry(3.6, 0.15, 1.8), deskTopMat);
    deskTop.position.y = 1.1;
    deskTop.castShadow = true;
    deskTop.receiveShadow = true;
    group.add(deskTop);

    // Metal Frame Legs
    const legMat = new THREE.MeshStandardMaterial({ color: 0x222226, metalness: 0.8, roughness: 0.2 });
    const legL = new THREE.Mesh(new THREE.BoxGeometry(0.15, 1.1, 1.7), legMat);
    legL.position.set(-1.65, 0.55, 0);
    legL.castShadow = true;
    group.add(legL);

    const legR = new THREE.Mesh(new THREE.BoxGeometry(0.15, 1.1, 1.7), legMat);
    legR.position.set(1.65, 0.55, 0);
    legR.castShadow = true;
    group.add(legR);

    // Dual Curved Ultrawide Monitors
    const screenFrameMat = new THREE.MeshStandardMaterial({ color: 0x111115, metalness: 0.9, roughness: 0.1 });
    const screenGlowMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });

    // Monitor 1 (Main)
    const mon1 = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.8, 0.05), screenFrameMat);
    mon1.position.set(-0.6, 1.7, -0.4);
    mon1.rotation.y = 0.15;
    mon1.castShadow = true;
    group.add(mon1);

    const screen1 = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 0.72), screenGlowMat);
    screen1.position.set(-0.6, 1.7, -0.37);
    screen1.rotation.y = 0.15;
    group.add(screen1);

    // Monitor 2 (Side vertical)
    const mon2 = new THREE.Mesh(new THREE.BoxGeometry(0.7, 1.1, 0.05), screenFrameMat);
    mon2.position.set(0.75, 1.85, -0.2);
    mon2.rotation.y = -0.3;
    mon2.castShadow = true;
    group.add(mon2);

    const screen2 = new THREE.Mesh(new THREE.PlaneGeometry(0.64, 1.02), screenGlowMat);
    screen2.position.set(0.75, 1.85, -0.17);
    screen2.rotation.y = -0.3;
    group.add(screen2);

    // Accessories (Keyboard, Coffee Cup, Ergonomic Chair)
    const keyboard = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.03, 0.3), screenFrameMat);
    keyboard.position.set(-0.4, 1.19, 0.2);
    group.add(keyboard);

    const cup = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.16, 16), new THREE.MeshStandardMaterial({ color: 0xffffff }));
    cup.position.set(0.9, 1.25, 0.4);
    group.add(cup);

    // Ergonomic Mesh Chair
    const chairSeat = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.1, 0.8), screenFrameMat);
    chairSeat.position.set(-0.4, 0.7, 0.9);
    chairSeat.castShadow = true;
    group.add(chairSeat);

    const chairBack = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.9, 0.1), screenFrameMat);
    chairBack.position.set(-0.4, 1.15, 1.3);
    chairBack.castShadow = true;
    group.add(chairBack);

    scene.add(group);
    stations.desk = { position: group.position, label: 'Desk 01', subtitle: 'Active Compute', dot: 'blue', agent: 'hermes' };
    create3DLabel('Desk 01', 'Active Compute', group.position, 2.7, 'blue', 'hermes');
}

// --- STATION 2: THE VAULT (SECURE STORAGE / CURADOR) ---
function buildStationVault() {
    const group = new THREE.Group();
    group.position.set(-4.5, 0, -3.2);

    const steelMat = new THREE.MeshStandardMaterial({ color: 0x64748b, metalness: 0.85, roughness: 0.2 });
    const chromeMat = new THREE.MeshStandardMaterial({ color: 0xd9e1e8, metalness: 0.95, roughness: 0.1 });
    const vaultGlowMat = new THREE.MeshBasicMaterial({ color: 0xf97316 });

    // Safe Body
    const safeBody = new THREE.Mesh(new THREE.BoxGeometry(2.4, 3.2, 2.0), steelMat);
    safeBody.position.y = 1.6;
    safeBody.castShadow = true;
    safeBody.receiveShadow = true;
    group.add(safeBody);

    // Open Door
    const door = new THREE.Mesh(new THREE.BoxGeometry(2.0, 3.0, 0.3), chromeMat);
    door.position.set(1.4, 1.6, 1.1);
    door.rotation.y = Math.PI / 3;
    door.castShadow = true;
    group.add(door);

    // Vault Wheel Handle
    const wheel = new THREE.Mesh(new THREE.TorusGeometry(0.35, 0.05, 16, 24), chromeMat);
    wheel.position.set(1.4, 1.6, 1.3);
    wheel.rotation.y = Math.PI / 3;
    group.add(wheel);

    // Glowing Inner Storage Cylinders
    for (let i = 0; i < 3; i++) {
        const cyl = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.6, 16), vaultGlowMat);
        cyl.position.set(-0.5 + i * 0.5, 1.2 + i * 0.4, 0.3);
        group.add(cyl);
    }

    scene.add(group);
    stations.vault = { position: group.position, label: 'Vault', subtitle: 'Secure Storage', dot: 'orange', agent: 'curador' };
    create3DLabel('Vault', 'Secure Storage', group.position, 3.8, 'orange', 'curador');
}

// --- STATION 3: KANBAN WALL (AGENTEPLAN) ---
function buildStationKanban() {
    const group = new THREE.Group();
    group.position.set(1.5, 0, -3.5);

    // Large Glass Whiteboard
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.8 });
    const boardMat = new THREE.MeshPhysicalMaterial({
        color: 0xffffff,
        roughness: 0.1,
        transmission: 0.4,
        opacity: 0.85,
        transparent: true
    });

    const frame = new THREE.Mesh(new THREE.BoxGeometry(4.6, 2.8, 0.1), frameMat);
    frame.position.y = 2.0;
    frame.castShadow = true;
    group.add(frame);

    const board = new THREE.Mesh(new THREE.PlaneGeometry(4.4, 2.6), boardMat);
    board.position.set(0, 2.0, 0.06);
    group.add(board);

    // Colorful Kanban Sticky Notes
    const colors = [0xfef08a, 0xa5f3fc, 0xfbcfe8, 0xc4b5fd];
    for (let col = 0; col < 4; col++) {
        for (let row = 0; row < 3; row++) {
            const cardColor = colors[(col + row) % colors.length];
            const cardMat = new THREE.MeshStandardMaterial({ color: cardColor, roughness: 0.6 });
            const card = new THREE.Mesh(new THREE.PlaneGeometry(0.45, 0.35), cardMat);
            card.position.set(-1.6 + col * 1.05, 2.7 - row * 0.55, 0.07);
            group.add(card);
        }
    }

    scene.add(group);
    stations.kanban = { position: group.position, label: 'Kanban Wall', subtitle: 'Work Items', dot: 'purple', agent: 'plan' };
    create3DLabel('Kanban Wall', 'Work Items', group.position, 3.8, 'purple', 'plan');
}

// --- STATION 4: STUDY BOARD & FLASHCARDS (AGENTEESTUDIO) ---
function buildStationStudy() {
    const group = new THREE.Group();
    group.position.set(4.8, 0, -1.0);

    const woodMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.3 });
    const cardGlowMat = new THREE.MeshBasicMaterial({ color: 0x10b981 });

    // Modern Bookshelf / Study Unit
    const shelf = new THREE.Mesh(new THREE.BoxGeometry(1.6, 3.2, 0.8), woodMat);
    shelf.position.y = 1.6;
    shelf.castShadow = true;
    shelf.receiveShadow = true;
    group.add(shelf);

    // Floating Hologram Flashcards
    for (let i = 0; i < 3; i++) {
        const fCard = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.4, 0.02), cardGlowMat);
        fCard.position.set(0, 1.2 + i * 0.7, 0.5 + i * 0.05);
        fCard.rotation.y = 0.2;
        group.add(fCard);
    }

    scene.add(group);
    stations.study = { position: group.position, label: 'Study Board', subtitle: 'SM-2 Learning', dot: 'green', agent: 'estudio' };
    create3DLabel('Study Board', 'SM-2 Learning', group.position, 3.6, 'green', 'estudio');
}

// --- STATION 5: SECURITY GATE (AGENTESYNC / DATAMASKER) ---
function buildStationSecurityGate() {
    const group = new THREE.Group();
    group.position.set(3.0, 0, 3.0);

    const metalMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.9, roughness: 0.2 });
    const glassMat = new THREE.MeshPhysicalMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.6, transmission: 0.8 });

    // Left & Right Turnstile Towers
    const towerL = new THREE.Mesh(new THREE.BoxGeometry(0.4, 1.3, 1.6), metalMat);
    towerL.position.set(-0.8, 0.65, 0);
    towerL.castShadow = true;
    group.add(towerL);

    const towerR = new THREE.Mesh(new THREE.BoxGeometry(0.4, 1.3, 1.6), metalMat);
    towerR.position.set(0.8, 0.65, 0);
    towerR.castShadow = true;
    group.add(towerR);

    // Glass Barrier Flap
    const barrier = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.8, 0.05), glassMat);
    barrier.position.set(0, 0.65, 0);
    group.add(barrier);

    scene.add(group);
    stations.gate = { position: group.position, label: 'Security Gate', subtitle: 'Access Control', dot: 'yellow', agent: 'sync' };
    create3DLabel('Security Gate', 'Access Control', group.position, 2.2, 'yellow', 'sync');
}

// --- SPAWN 3D AVATAR ROBOTS ---
function spawnAllAgents() {
    Object.keys(AGENT_CONFIGS).forEach(key => {
        const conf = AGENT_CONFIGS[key];
        const robot = createRobotAvatar(conf.color, key);
        robot.position.set(conf.position.x, conf.position.y, conf.position.z);
        scene.add(robot);
        agents[key] = { mesh: robot, config: conf, isTyping: false };
    });
}

function createRobotAvatar(bodyColorHex, agentId) {
    const group = new THREE.Group();
    group.name = `agent_${agentId}`;

    const bodyMat = new THREE.MeshStandardMaterial({ color: bodyColorHex, roughness: 0.2, metalness: 0.1 });
    const whiteMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.2 });
    const visorMat = new THREE.MeshBasicMaterial({ color: 0x0f172a });
    const eyeGlowMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });

    // Torso (Cute Capsule/Sphere)
    const torso = new THREE.Mesh(new THREE.SphereGeometry(0.38, 24, 24), bodyMat);
    torso.position.y = 0.55;
    torso.castShadow = true;
    group.add(torso);

    // White Chest Plate
    const chest = new THREE.Mesh(new THREE.SphereGeometry(0.24, 16, 16), whiteMat);
    chest.position.set(0, 0.55, 0.18);
    group.add(chest);

    // Head
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.32, 24, 24), bodyMat);
    head.position.y = 1.05;
    head.castShadow = true;
    group.add(head);

    // Dark Visor Face
    const visor = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.18, 0.1), visorMat);
    visor.position.set(0, 1.05, 0.26);
    group.add(visor);

    // Glowing Eyes
    const eyeL = new THREE.Mesh(new THREE.SphereGeometry(0.04, 12, 12), eyeGlowMat);
    eyeL.position.set(-0.09, 1.05, 0.32);
    group.add(eyeL);

    const eyeR = new THREE.Mesh(new THREE.SphereGeometry(0.04, 12, 12), eyeGlowMat);
    eyeR.position.set(0.09, 1.05, 0.32);
    group.add(eyeR);

    // Floating Base / Soft Shadow
    const shadowGeo = new THREE.CircleGeometry(0.32, 24);
    const shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.2 });
    const shadow = new THREE.Mesh(shadowGeo, shadowMat);
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.02;
    group.add(shadow);

    return group;
}

// --- 3D FLOATING HTML LABELS ---
function create3DLabel(title, subtitle, pos3d, heightOffset, dotColor, agentId) {
    const el = document.createElement('div');
    el.className = 'station-pill';
    el.innerHTML = `<span class="station-dot ${dotColor}"></span><span>${title} <small style="opacity:0.6;font-weight:400;">${subtitle}</small></span>`;
    el.onclick = () => selectAgent(agentId);
    labelsLayer.appendChild(el);

    stationLabels.push({ element: el, position: new THREE.Vector3(pos3d.x, pos3d.y + heightOffset, pos3d.z) });
}

function update3DLabels() {
    const halfWidth = window.innerWidth / 2;
    const halfHeight = window.innerHeight / 2;

    stationLabels.forEach(item => {
        const wp = item.position.clone();
        wp.project(camera);

        // Check if behind camera
        if (wp.z > 1) {
            item.element.style.display = 'none';
        } else {
            item.element.style.display = 'flex';
            const x = (wp.x * halfWidth) + halfWidth;
            const y = -(wp.y * halfHeight) + halfHeight;
            item.element.style.left = `${x}px`;
            item.element.style.top = `${y}px`;
        }
    });
}

// --- INTERACTIVE SELECTION & TELEMETRY ---
window.selectAgent = function(agentKey) {
    if (!AGENT_CONFIGS[agentKey]) return;
    selectedAgentKey = agentKey;
    const conf = AGENT_CONFIGS[agentKey];

    // Highlight Roster
    document.querySelectorAll('.roster-item').forEach(el => el.classList.remove('active'));
    const rosterIdx = ['hermes', 'curador', 'plan', 'estudio', 'sync'].indexOf(agentKey);
    if (rosterIdx >= 0 && document.querySelectorAll('.roster-item')[rosterIdx]) {
        document.querySelectorAll('.roster-item')[rosterIdx].classList.add('active');
    }

    // Update Bottom Telemetry Card
    const card = document.getElementById('telemetryCard');
    card.classList.remove('hidden');
    document.getElementById('cardAgentName').textContent = conf.badge;
    document.getElementById('cardTask').textContent = conf.task;
    document.getElementById('cardFeature').textContent = conf.feature;
    document.querySelector('.active-agent-badge .dot-indicator').style.backgroundColor = conf.accentCss;
    document.querySelector('.active-agent-badge .dot-indicator').style.boxShadow = `0 0 10px ${conf.accentCss}`;

    // Focus Camera on Selected Agent
    const targetAgent = agents[agentKey];
    if (targetAgent) {
        panCameraTo(targetAgent.mesh.position.x + 5, targetAgent.mesh.position.y + 6, targetAgent.mesh.position.z + 7, targetAgent.mesh.position);
    }
};

window.closeTelemetry = function() {
    document.getElementById('telemetryCard').classList.add('hidden');
};

// --- CAMERA PRESET CONTROLS ---
window.focusCamera = function(viewName) {
    if (viewName === 'overview') {
        panCameraTo(16, 15, 18, new THREE.Vector3(0, 0.5, 0));
    } else if (viewName === 'desk') {
        selectAgent('hermes');
    } else if (viewName === 'vault') {
        selectAgent('curador');
    } else if (viewName === 'kanban') {
        selectAgent('plan');
    } else if (viewName === 'study') {
        selectAgent('estudio');
    }
};

function panCameraTo(x, y, z, targetLookAt) {
    new TWEEN.Tween(camera.position)
        .to({ x: x, y: y, z: z }, 1000)
        .easing(TWEEN.Easing.Cubic.Out)
        .start();

    new TWEEN.Tween(controls.target)
        .to({ x: targetLookAt.x, y: targetLookAt.y, z: targetLookAt.z }, 1000)
        .easing(TWEEN.Easing.Cubic.Out)
        .start();
}

// --- RAYCASTING CLICK DETECTION ---
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

function onCanvasClick(event) {
    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);

    const intersects = raycaster.intersectObjects(scene.children, true);
    if (intersects.length > 0) {
        let current = intersects[0].object;
        while (current && current.parent && current.parent !== scene) {
            if (current.name && current.name.startsWith('agent_')) {
                const agentKey = current.name.replace('agent_', '');
                selectAgent(agentKey);
                return;
            }
            current = current.parent;
        }
    }
}

// --- TASK SIMULATION & AUTO ROAM ---
window.triggerTaskSimulation = function() {
    const card = document.getElementById('telemetryCard');
    card.classList.remove('hidden');

    const fill = document.getElementById('cardProgressFill');
    const num = document.getElementById('cardProgressNum');
    fill.style.width = '10%';
    num.textContent = '10%';

    let p = 10;
    const interval = setInterval(() => {
        p += 15;
        if (p >= 100) {
            p = 100;
            clearInterval(interval);
            tokenCounter += Math.floor(Math.random() * 850 + 200);
            document.getElementById('cardTokens').textContent = tokenCounter.toLocaleString();
        }
        fill.style.width = `${p}%`;
        num.textContent = `${p}%`;
    }, 250);

    // Animate Active Agent Bobbing
    const active = agents[selectedAgentKey];
    if (active) {
        new TWEEN.Tween(active.mesh.position)
            .to({ y: 1.1 }, 200)
            .yoyo(true)
            .repeat(5)
            .start();
    }
};

window.toggleAutoRoam = function() {
    isAutoRoam = !isAutoRoam;
    const btn = document.getElementById('roamBtn');
    btn.textContent = isAutoRoam ? '⏹️ Detener Paseo' : '🚶 Activar Modo Paseo';
    btn.style.borderColor = isAutoRoam ? '#3b82f6' : '';
};

// --- DARK / DAY THEME TOGGLE ---
window.toggleLightingMode = function() {
    isDarkMode = !isDarkMode;
    document.body.classList.toggle('dark-mode', isDarkMode);
    document.getElementById('themeToggle').textContent = isDarkMode ? '☀️ Día' : '🌙 Noche';

    const bgColor = isDarkMode ? 0x090d16 : 0xeef2f6;
    scene.background.setHex(bgColor);
    scene.fog.color.setHex(bgColor);
    ambientLight.intensity = isDarkMode ? 0.35 : 0.75;
    dirLight.intensity = isDarkMode ? 0.45 : 0.85;
};

// --- TELEMETRY TICKER ---
function startTelemetryTicker() {
    setInterval(() => {
        const elapsedSec = (Date.now() - startTime) / 1000;
        const mins = Math.floor(elapsedSec / 60).toString().padStart(2, '0');
        const secs = (elapsedSec % 60).toFixed(1).padStart(4, '0');
        document.getElementById('cardRuntime').textContent = `${mins}:${secs}s`;
    }, 100);
}

// --- WINDOW RESIZE ---
function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

// --- ANIMATION LOOP ---
let clock = new THREE.Clock();

function animate() {
    requestAnimationFrame(animate);
    const elapsedTime = clock.getElapsedTime();
    TWEEN.update();

    // Idle Floating/Breathing Animation for all Agents
    Object.keys(agents).forEach((key, idx) => {
        const ag = agents[key];
        ag.mesh.position.y = ag.config.position.y + Math.sin(elapsedTime * 2.5 + idx) * 0.05;

        // Auto Roam Behavior
        if (isAutoRoam && Math.random() < 0.008) {
            const rx = ag.config.position.x + (Math.random() - 0.5) * 2.5;
            const rz = ag.config.position.z + (Math.random() - 0.5) * 2.5;
            new TWEEN.Tween(ag.mesh.position)
                .to({ x: rx, z: rz }, 1800)
                .easing(TWEEN.Easing.Quadratic.InOut)
                .start();
        }
    });

    controls.update();
    update3DLabels();
    renderer.render(scene, camera);
}

// Start on DOM Loaded
window.addEventListener('DOMContentLoaded', init);
