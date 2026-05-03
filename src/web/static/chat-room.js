const roomId = document.body.dataset.roomId;
const maxMessageLength = Number(document.body.dataset.maxMessageLength || "500");
const ROOM_MODE = "closed_roster_openpgp_v1";

const STORAGE_KEYS = {
    identity: "closed_roster_identity_v1",
    identityBackup: "closed_roster_identity_backup_v1",
    trust: "closed_roster_trust_v1",
    warningAccepted: "closed_roster_warning_accepted_v1",
    draftPrefix: "closed_roster_draft_v1:",
};

const dom = {
    acceptSecurityWarningBtn: document.getElementById("acceptSecurityWarningBtn"),
    addPeerBtn: document.getElementById("addPeerBtn"),
    bootstrapPanel: document.getElementById("bootstrapPanel"),
    clearIdentityBtn: document.getElementById("clearIdentityBtn"),
    composerState: document.getElementById("composerState"),
    copyPublicKeyBtn: document.getElementById("copyPublicKeyBtn"),
    draftRosterList: document.getElementById("draftRosterList"),
    downloadPrivateKeyBtn: document.getElementById("downloadPrivateKeyBtn"),
    displayNameInput: document.getElementById("displayNameInput"),
    epochSummary: document.getElementById("epochSummary"),
    generateIdentityBtn: document.getElementById("generateIdentityBtn"),
    identityPassphraseInput: document.getElementById("identityPassphraseInput"),
    identityRecovery: document.getElementById("identityRecovery"),
    identitySummary: document.getElementById("identitySummary"),
    importIdentityBtn: document.getElementById("importIdentityBtn"),
    lockRosterBtn: document.getElementById("lockRosterBtn"),
    memberIdInput: document.getElementById("memberIdInput"),
    messageInput: document.getElementById("messageInput"),
    messagesContainer: document.getElementById("messagesContainer"),
    peerDisplayNameInput: document.getElementById("peerDisplayNameInput"),
    peerMemberIdInput: document.getElementById("peerMemberIdInput"),
    peerPublicKeyInput: document.getElementById("peerPublicKeyInput"),
    privateKeyInput: document.getElementById("privateKeyInput"),
    publicKeyOutput: document.getElementById("publicKeyOutput"),
    roomAlerts: document.getElementById("roomAlerts"),
    roomMode: document.getElementById("roomMode"),
    rosterList: document.getElementById("rosterList"),
    securityWarning: document.getElementById("securityWarning"),
    sendBtn: document.getElementById("sendBtn"),
    statusMsg: document.getElementById("statusMsg"),
    userCount: document.getElementById("userCount"),
};

const state = {
    identityBackup: loadSessionJson(STORAGE_KEYS.identityBackup, null),
    cachedPassphrase: null,
    draftMembers: loadSessionJson(getDraftStorageKey(), []),
    keyCache: null,
    keyCacheHash: null,
    localIdentity: loadSessionJson(STORAGE_KEYS.identity, null),
    pollInterval: null,
    roomState: null,
    securityWarningAccepted: sessionStorage.getItem(STORAGE_KEYS.warningAccepted) === "true",
    trustStore: loadSessionJson(STORAGE_KEYS.trust, { identities: {} }),
};

const RANDOM_IDENTITY_ADJECTIVES = [
    "Swift",
    "Silent",
    "Dark",
    "Ghost",
    "Shadow",
    "Phantom",
    "Cipher",
    "Echo",
    "Rogue",
    "Viper",
    "Stealth",
    "Void",
];

const RANDOM_IDENTITY_NOUNS = [
    "Raven",
    "Wolf",
    "Fox",
    "Hawk",
    "Lynx",
    "Owl",
    "Cobra",
    "Tiger",
    "Falcon",
    "Spider",
    "Serpent",
    "Dragon",
];

if (!Array.isArray(state.draftMembers)) {
    state.draftMembers = [];
}

if (!state.trustStore || typeof state.trustStore !== "object" || !state.trustStore.identities) {
    state.trustStore = { identities: {} };
}

let statusTimer = null;

function getDraftStorageKey() {
    return `${STORAGE_KEYS.draftPrefix}${roomId}`;
}

function loadSessionJson(key, fallbackValue) {
    try {
        const raw = sessionStorage.getItem(key);
        if (!raw) {
            return fallbackValue;
        }
        return JSON.parse(raw);
    } catch (error) {
        return fallbackValue;
    }
}

function saveSessionJson(key, value) {
    sessionStorage.setItem(key, JSON.stringify(value));
}

function clearSessionJson(key) {
    sessionStorage.removeItem(key);
}

function getRandomUint32() {
    if (window.crypto && typeof window.crypto.getRandomValues === "function") {
        const values = new Uint32Array(1);
        window.crypto.getRandomValues(values);
        return values[0];
    }
    return Math.floor(Math.random() * 0x100000000);
}

function chooseRandom(list) {
    return list[getRandomUint32() % list.length];
}

function generateRandomIdentitySuggestion() {
    const adjective = chooseRandom(RANDOM_IDENTITY_ADJECTIVES);
    const noun = chooseRandom(RANDOM_IDENTITY_NOUNS);
    const number = String(getRandomUint32() % 10000).padStart(4, "0");

    return {
        memberId: `${adjective}-${noun}-${number}`.toLowerCase(),
        displayName: `${adjective} ${noun} ${number}`,
    };
}

function saveTrustStore() {
    saveSessionJson(STORAGE_KEYS.trust, state.trustStore);
}

function saveDraftMembers() {
    saveSessionJson(getDraftStorageKey(), state.draftMembers);
}

function sameIdentity(left, right) {
    if (!left || !right) {
        return false;
    }
    return (
        left.member_id === right.member_id &&
        left.signing_fingerprint === right.signing_fingerprint &&
        left.encryption_fingerprint === right.encryption_fingerprint
    );
}

function backupMatchesIdentity(meta, identity) {
    if (!meta || !identity) {
        return false;
    }
    return (
        meta.member_id === identity.member_id &&
        meta.signing_fingerprint === identity.signing_fingerprint &&
        meta.encryption_fingerprint === identity.encryption_fingerprint
    );
}

function saveIdentityBackup(meta) {
    state.identityBackup = meta;
    if (meta) {
        saveSessionJson(STORAGE_KEYS.identityBackup, meta);
    } else {
        clearSessionJson(STORAGE_KEYS.identityBackup);
    }
}

function saveLocalIdentity(identity) {
    const preserveBackup =
        sameIdentity(state.localIdentity, identity) ||
        backupMatchesIdentity(state.identityBackup, identity)
            ? state.identityBackup
            : null;
    state.localIdentity = identity;
    saveSessionJson(STORAGE_KEYS.identity, identity);
    saveIdentityBackup(preserveBackup);
}

function clearLocalIdentityState() {
    state.cachedPassphrase = null;
    state.keyCache = null;
    state.keyCacheHash = null;
    state.localIdentity = null;
    clearSessionJson(STORAGE_KEYS.identity);
}

function showStatus(message, duration) {
    dom.statusMsg.textContent = message || "";
    if (statusTimer) {
        clearTimeout(statusTimer);
        statusTimer = null;
    }
    if (message && duration !== 0) {
        statusTimer = setTimeout(() => {
            dom.statusMsg.textContent = "";
            statusTimer = null;
        }, duration || 4500);
    }
}

function normalizeUpperSet(values) {
    return Array.from(
        new Set(
            (values || []).map((value) => String(value).trim().toUpperCase()).filter(Boolean)
        )
    ).sort();
}

function arraysEqualAsSets(left, right) {
    const leftNormalized = normalizeUpperSet(left);
    const rightNormalized = normalizeUpperSet(right);
    if (leftNormalized.length !== rightNormalized.length) {
        return false;
    }
    return leftNormalized.every((value, index) => value === rightNormalized[index]);
}

function truncateMiddle(value, keepChars) {
    if (!value) {
        return "";
    }
    const width = keepChars || 12;
    if (value.length <= width * 2) {
        return value;
    }
    return `${value.slice(0, width)}...${value.slice(-width)}`;
}

function formatDateTime(timestamp) {
    if (!timestamp) {
        return "";
    }
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
        return String(timestamp);
    }
    return date.toLocaleString([], {
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function escapeForText(value) {
    return String(value == null ? "" : value);
}

function getActiveEpoch() {
    return state.roomState && state.roomState.active_epoch ? state.roomState.active_epoch : null;
}

function getLocalIdentityProjection() {
    if (!state.localIdentity) {
        return null;
    }
    return {
        member_id: state.localIdentity.member_id,
        display_name: state.localIdentity.display_name,
        signing_fingerprint: state.localIdentity.signing_fingerprint,
        encryption_fingerprint: state.localIdentity.encryption_fingerprint,
        signing_key_id: state.localIdentity.signing_key_id,
        encryption_key_id: state.localIdentity.encryption_key_id,
        public_key_armored: state.localIdentity.public_key_armored,
    };
}

function getTrustStatusForRecord(record) {
    const existing = state.trustStore.identities[record.member_id];
    if (!existing) {
        return "new";
    }
    if (
        existing.signing_fingerprint !== record.signing_fingerprint ||
        existing.encryption_fingerprint !== record.encryption_fingerprint
    ) {
        return "changed";
    }
    return existing.verified ? "verified" : "known";
}

function observeTrustRecord(record) {
    const existing = state.trustStore.identities[record.member_id];
    if (!existing) {
        state.trustStore.identities[record.member_id] = {
            ...record,
            verified: false,
        };
        return "new";
    }

    if (
        existing.signing_fingerprint !== record.signing_fingerprint ||
        existing.encryption_fingerprint !== record.encryption_fingerprint
    ) {
        return "changed";
    }

    state.trustStore.identities[record.member_id] = {
        ...existing,
        display_name: record.display_name,
        public_key_armored: record.public_key_armored,
        signing_key_id: record.signing_key_id,
        encryption_key_id: record.encryption_key_id,
    };
    return existing.verified ? "verified" : "known";
}

function markTrustVerified(record) {
    state.trustStore.identities[record.member_id] = {
        ...record,
        verified: true,
    };
    saveTrustStore();
}

function removeDraftMember(memberId) {
    state.draftMembers = state.draftMembers.filter((member) => member.member_id !== memberId);
    saveDraftMembers();
}

function syncIdentityInputs() {
    if (!state.localIdentity) {
        return;
    }
    dom.memberIdInput.value = state.localIdentity.member_id || "";
    dom.displayNameInput.value = state.localIdentity.display_name || "";
    dom.publicKeyOutput.value = state.localIdentity.public_key_armored || "";
}

function prepopulateIdentityInputs() {
    if (state.localIdentity) {
        syncIdentityInputs();
        return;
    }

    const memberId = String(dom.memberIdInput.value || "").trim();
    const displayName = String(dom.displayNameInput.value || "").trim();
    if (memberId && displayName) {
        return;
    }

    const suggestion = generateRandomIdentitySuggestion();
    if (!memberId) {
        dom.memberIdInput.value = suggestion.memberId;
    }
    if (!displayName) {
        dom.displayNameInput.value = suggestion.displayName;
    }
}

function renderIdentitySummary() {
    if (!state.localIdentity) {
        dom.identitySummary.textContent =
            "No local identity configured.\nGenerate or import a private key, then verify that its member ID matches the roster.";
        dom.publicKeyOutput.value = "";
        return;
    }

    dom.publicKeyOutput.value = state.localIdentity.public_key_armored || "";
    dom.identitySummary.textContent = [
        `Member ID: ${state.localIdentity.member_id}`,
        `Display Name: ${state.localIdentity.display_name}`,
        `Signing Fingerprint: ${state.localIdentity.signing_fingerprint}`,
        `Encryption Fingerprint: ${state.localIdentity.encryption_fingerprint}`,
        `Signing Key ID: ${state.localIdentity.signing_key_id}`,
        `Encryption Key ID: ${state.localIdentity.encryption_key_id}`,
        `Private Key: ${state.localIdentity.private_key_protected ? "Passphrase protected" : "Stored for this session"}`,
        `Backup Export: ${state.identityBackup && state.identityBackup.downloaded_at ? formatDateTime(state.identityBackup.downloaded_at) : "Not downloaded in this browser session"}`,
    ].join("\n");
}

function renderIdentityRecovery() {
    if (!dom.identityRecovery) {
        return;
    }

    if (!state.localIdentity) {
        dom.identityRecovery.textContent = [
            "Recovery:",
            "Keep an armored private-key backup outside this browser.",
            "To restore access after a reload or browser close, paste that armored private key into the Private Key field and click Import Private Key.",
            "If the key itself changes, stop using the room and create a new room with a new roster bootstrap.",
        ].join("\n");
        return;
    }

    const backupStatus =
        state.identityBackup && state.identityBackup.downloaded_at
            ? `Last private-key export: ${formatDateTime(state.identityBackup.downloaded_at)}`
            : "No private-key export recorded for this browser session yet.";

    dom.identityRecovery.textContent = [
        backupStatus,
        "Recovery:",
        "Download the armored private key now and store it somewhere you control.",
        "If this browser session disappears, re-import the same armored private key and re-enter the passphrase if the key is protected.",
        "If you ever need to rotate keys, do not keep using the current room. Create a new room and bootstrap a new roster.",
    ].join("\n");
}

function createBadge(label, className) {
    const badge = document.createElement("span");
    badge.className = className ? `badge ${className}` : "badge";
    badge.textContent = label;
    return badge;
}

function buildRosterItem(record, status, options) {
    const item = document.createElement("div");
    item.className = "roster-item";

    const main = document.createElement("div");
    main.className = "roster-main";

    const nameBox = document.createElement("div");
    nameBox.className = "roster-name";

    const title = document.createElement("div");
    title.className = "roster-title";
    title.textContent = `${record.display_name} (${record.member_id})`;

    const subtitle = document.createElement("div");
    subtitle.className = "roster-subtitle";
    subtitle.textContent = `Signing key ${record.signing_key_id} | Encryption key ${record.encryption_key_id}`;

    nameBox.appendChild(title);
    nameBox.appendChild(subtitle);
    main.appendChild(nameBox);

    const badgeRow = document.createElement("div");
    badgeRow.className = "badge-row";

    if (options.isLocal) {
        badgeRow.appendChild(createBadge("Local", "local"));
    }
    if (status === "verified") {
        badgeRow.appendChild(createBadge("Verified", "verified"));
    } else if (status === "changed") {
        badgeRow.appendChild(createBadge("Changed Key", "changed"));
    } else {
        badgeRow.appendChild(createBadge("Pending Verification", "pending"));
    }

    if (options.isDraft) {
        badgeRow.appendChild(createBadge("Draft", null));
    }

    main.appendChild(badgeRow);
    item.appendChild(main);

    const fingerprints = document.createElement("div");
    fingerprints.className = "fingerprints";
    fingerprints.textContent = [
        `Signing Fingerprint: ${record.signing_fingerprint}`,
        `Encryption Fingerprint: ${record.encryption_fingerprint}`,
    ].join("\n");
    item.appendChild(fingerprints);

    const actions = document.createElement("div");
    actions.className = "roster-actions";

    if (options.action === "verify") {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "roster-action";
        button.dataset.action = options.isDraft ? "verify-draft" : "verify-active";
        button.dataset.memberId = record.member_id;
        button.textContent = status === "changed" && options.isDraft ? "Replace + Verify" : "Mark Verified";
        actions.appendChild(button);
    }

    if (options.isDraft) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "roster-action secondary";
        button.dataset.action = "remove-draft";
        button.dataset.memberId = record.member_id;
        button.textContent = "Remove";
        actions.appendChild(button);
    }

    if (actions.children.length > 0) {
        item.appendChild(actions);
    }

    return item;
}

function renderDraftRoster() {
    const activeEpoch = getActiveEpoch();
    dom.bootstrapPanel.hidden = Boolean(activeEpoch);
    dom.draftRosterList.replaceChildren();

    if (activeEpoch) {
        return;
    }

    if (!state.draftMembers.length) {
        const empty = document.createElement("div");
        empty.className = "summary-box";
        empty.textContent =
            "No draft members yet. Add every participant's public key, then mark each one verified after the out-of-band fingerprint check.";
        dom.draftRosterList.appendChild(empty);
        return;
    }

    state.draftMembers.forEach((record) => {
        const status = getTrustStatusForRecord(record);
        const item = buildRosterItem(record, status, {
            action: status === "verified" ? null : "verify",
            isDraft: true,
            isLocal: false,
        });
        dom.draftRosterList.appendChild(item);
    });
}

function localIdentityMatchesRosterMember(member) {
    return Boolean(
        state.localIdentity &&
        member &&
        state.localIdentity.member_id === member.member_id &&
        state.localIdentity.signing_fingerprint === member.signing_fingerprint &&
        state.localIdentity.encryption_fingerprint === member.encryption_fingerprint
    );
}

function getLocalRosterMember() {
    const activeEpoch = getActiveEpoch();
    if (!activeEpoch || !state.localIdentity) {
        return null;
    }

    const member = activeEpoch.members.find((item) => item.member_id === state.localIdentity.member_id);
    if (!member) {
        return null;
    }
    return localIdentityMatchesRosterMember(member) ? member : null;
}

function renderActiveEpoch() {
    const activeEpoch = getActiveEpoch();
    dom.rosterList.replaceChildren();

    if (!activeEpoch) {
        dom.epochSummary.textContent =
            "This room has no active epoch yet.\nAdd every roster member, verify fingerprints locally, and lock epoch 1 before sending anything.";
        return;
    }

    dom.epochSummary.textContent = [
        `Epoch: ${activeEpoch.epoch}`,
        `Roster Hash: ${activeEpoch.roster_hash}`,
        `Members: ${activeEpoch.members.length}`,
        "Membership changes: disabled in this alpha release",
    ].join("\n");

    activeEpoch.members.forEach((member) => {
        const status = getTrustStatusForRecord(member);
        const isLocal = localIdentityMatchesRosterMember(member);
        const item = buildRosterItem(member, status, {
            action: !isLocal && (status === "new" || status === "known") ? "verify" : null,
            isDraft: false,
            isLocal,
        });
        dom.rosterList.appendChild(item);
    });
}

function renderRoomAlerts() {
    const activeEpoch = getActiveEpoch();
    const alerts = [];

    if (!activeEpoch) {
        alerts.push({
            tone: "info",
            text: "Room not bootstrapped yet. Lock the roster only after every participant has exchanged and verified fingerprints out of band.",
        });
    } else {
        alerts.push({
            tone: "info",
            text: "Active roster is immutable in this alpha release. To add, remove, or rotate a member key, create a new room and a new epoch-1 roster.",
        });
    }

    if (!state.localIdentity) {
        alerts.push({
            tone: "danger",
            text: "No local identity is configured. Import or generate the key pair you use in this room before you try to decrypt or send messages.",
        });
    } else if (!(state.identityBackup && state.identityBackup.downloaded_at)) {
        alerts.push({
            tone: "warning",
            text: "No private-key backup export is recorded for this browser session. Download the armored private key before you rely on this room.",
        });
    } else if (activeEpoch) {
        const declaredMember = activeEpoch.members.find(
            (member) => member.member_id === state.localIdentity.member_id
        );

        if (!declaredMember) {
            alerts.push({
                tone: "danger",
                text: `Local identity ${state.localIdentity.member_id} is not part of the active roster.`,
            });
        } else if (!localIdentityMatchesRosterMember(declaredMember)) {
            alerts.push({
                tone: "danger",
                text: "Local identity fingerprints do not match the active roster entry. Stop and confirm the correct key out of band.",
            });
        }
    }

    if (activeEpoch) {
        const changedMembers = activeEpoch.members.filter(
            (member) => getTrustStatusForRecord(member) === "changed"
        );
        if (changedMembers.length) {
            alerts.push({
                tone: "danger",
                text: `Key change detected for ${changedMembers.map((member) => member.member_id).join(", ")}. Do not keep using this room.`,
            });
        }

        const pendingMembers = activeEpoch.members.filter((member) => {
            if (localIdentityMatchesRosterMember(member)) {
                return false;
            }
            const status = getTrustStatusForRecord(member);
            return status === "new" || status === "known";
        });
        if (pendingMembers.length) {
            alerts.push({
                tone: "warning",
                text: `Pending local verification: ${pendingMembers.map((member) => member.member_id).join(", ")}.`,
            });
        }
    }

    dom.roomAlerts.replaceChildren();
    alerts.forEach((alert) => {
        const box = document.createElement("div");
        box.className = `alert ${alert.tone}`;
        box.textContent = alert.text;
        dom.roomAlerts.appendChild(box);
    });
}

function getSendReadiness() {
    const activeEpoch = getActiveEpoch();
    if (!state.securityWarningAccepted) {
        return {
            ready: false,
            message: "Acknowledge the room rules before sending anything.",
        };
    }
    if (!activeEpoch) {
        return {
            ready: false,
            message: "Bootstrap the room roster before messaging.",
        };
    }
    if (!state.localIdentity) {
        return {
            ready: false,
            message: "Generate or import your local identity first.",
        };
    }
    if (!getLocalRosterMember()) {
        return {
            ready: false,
            message: "Local identity must exactly match an active roster member.",
        };
    }

    const changedMembers = activeEpoch.members.filter(
        (member) => getTrustStatusForRecord(member) === "changed"
    );
    if (changedMembers.length) {
        return {
            ready: false,
            message: "Key change detected in the roster. Stop and create a new room.",
        };
    }

    const unverifiedMembers = activeEpoch.members.filter((member) => {
        if (localIdentityMatchesRosterMember(member)) {
            return false;
        }
        return getTrustStatusForRecord(member) !== "verified";
    });
    if (unverifiedMembers.length) {
        return {
            ready: false,
            message: "Verify every non-local roster member out of band before sending.",
        };
    }

    return {
        ready: true,
        message: "Ready: this message will be signed and encrypted to the full roster.",
    };
}

function updateComposerState() {
    const readiness = getSendReadiness();
    dom.composerState.textContent = readiness.message;
    dom.sendBtn.disabled = !readiness.ready;
    dom.messageInput.disabled = !readiness.ready;
}

function renderAll() {
    renderIdentitySummary();
    renderIdentityRecovery();
    renderDraftRoster();
    renderActiveEpoch();
    renderRoomAlerts();
    updateComposerState();
}

async function derivePublicRecordFromKey(publicKeyArmored, memberId, displayName) {
    if (!window.openpgp) {
        throw new Error("OpenPGP.js did not load");
    }

    const trimmedPublicKey = String(publicKeyArmored || "").trim();
    const normalizedMemberId = String(memberId || "").trim();
    const normalizedDisplayName = String(displayName || normalizedMemberId).trim();

    if (!normalizedMemberId) {
        throw new Error("Member ID is required");
    }
    if (!trimmedPublicKey) {
        throw new Error("Public key is required");
    }

    const publicKey = await openpgp.readKey({ armoredKey: trimmedPublicKey });
    const signingKey = await publicKey.getSigningKey();
    const encryptionKey = await publicKey.getEncryptionKey();

    return {
        member_id: normalizedMemberId,
        display_name: normalizedDisplayName || normalizedMemberId,
        public_key_armored: trimmedPublicKey,
        signing_fingerprint: signingKey.getFingerprint().toUpperCase(),
        encryption_fingerprint: encryptionKey.getFingerprint().toUpperCase(),
        signing_key_id: signingKey.getKeyID().toHex().toUpperCase(),
        encryption_key_id: encryptionKey.getKeyID().toHex().toUpperCase(),
    };
}

async function prepareLocalIdentityFromPrivateKey(privateKeyArmored, memberId, displayName, passphrase) {
    const trimmedPrivateKey = String(privateKeyArmored || "").trim();
    if (!trimmedPrivateKey) {
        throw new Error("Private key is required");
    }

    const rawPrivateKey = await openpgp.readPrivateKey({ armoredKey: trimmedPrivateKey });
    const needsPassphrase = !rawPrivateKey.isDecrypted();
    let decryptedPrivateKey = rawPrivateKey;

    if (needsPassphrase) {
        if (!passphrase) {
            throw new Error("This private key is passphrase protected. Enter the passphrase to import it.");
        }
        decryptedPrivateKey = await openpgp.decryptKey({
            privateKey: rawPrivateKey,
            passphrase,
        });
        state.cachedPassphrase = passphrase;
    } else {
        state.cachedPassphrase = null;
    }

    const publicKeyArmored = decryptedPrivateKey.toPublic().armor();
    const publicRecord = await derivePublicRecordFromKey(publicKeyArmored, memberId, displayName);

    return {
        ...publicRecord,
        private_key_armored: trimmedPrivateKey,
        private_key_protected: needsPassphrase,
    };
}

async function getUnlockedPrivateKey() {
    if (!state.localIdentity || !state.localIdentity.private_key_armored) {
        throw new Error("No local private key is configured");
    }

    let privateKey = await openpgp.readPrivateKey({
        armoredKey: state.localIdentity.private_key_armored,
    });

    if (privateKey.isDecrypted()) {
        return privateKey;
    }

    const passphrase =
        state.cachedPassphrase ||
        String(dom.identityPassphraseInput.value || "").trim();

    if (!passphrase) {
        throw new Error("Enter the private-key passphrase to decrypt room messages");
    }

    privateKey = await openpgp.decryptKey({
        privateKey,
        passphrase,
    });
    state.cachedPassphrase = passphrase;
    return privateKey;
}

async function ensureRoomKeyCache() {
    const activeEpoch = getActiveEpoch();
    if (!activeEpoch) {
        return {};
    }

    if (state.keyCache && state.keyCacheHash === activeEpoch.roster_hash) {
        return state.keyCache;
    }

    const keyMap = {};
    for (const member of activeEpoch.members) {
        keyMap[member.member_id] = await openpgp.readKey({
            armoredKey: member.public_key_armored,
        });
    }

    state.keyCache = keyMap;
    state.keyCacheHash = activeEpoch.roster_hash;
    return keyMap;
}

function getExpectedRecipientFingerprints(activeEpoch) {
    return activeEpoch.members.map((member) => member.encryption_fingerprint);
}

function getExpectedRecipientKeyIds(activeEpoch) {
    return activeEpoch.members.map((member) => member.encryption_key_id);
}

async function generateLocalIdentity() {
    const memberId = String(dom.memberIdInput.value || "").trim();
    const displayName = String(dom.displayNameInput.value || "").trim() || memberId;
    const passphrase = String(dom.identityPassphraseInput.value || "").trim();

    if (!memberId) {
        showStatus("Member ID is required before generating a key pair.", 5000);
        return;
    }

    dom.generateIdentityBtn.disabled = true;
    try {
        const generated = await openpgp.generateKey({
            userIDs: [{ name: displayName }],
            type: "ecc",
            curve: "curve25519",
            format: "armored",
            passphrase: passphrase || undefined,
        });

        dom.privateKeyInput.value = generated.privateKey;
        const identity = await prepareLocalIdentityFromPrivateKey(
            generated.privateKey,
            memberId,
            displayName,
            passphrase
        );

        saveLocalIdentity(identity);
        markTrustVerified(getLocalIdentityProjection());
        syncIdentityInputs();
        renderAll();
        showStatus("Generated a local key pair. Share only the public key with roster members.", 6000);
    } catch (error) {
        showStatus(`Key generation failed: ${error.message}`, 7000);
    } finally {
        dom.generateIdentityBtn.disabled = false;
    }
}

async function importLocalIdentity() {
    const memberId = String(dom.memberIdInput.value || "").trim();
    const displayName = String(dom.displayNameInput.value || "").trim() || memberId;
    const passphrase = String(dom.identityPassphraseInput.value || "").trim();
    const privateKeyArmored = dom.privateKeyInput.value;

    if (!memberId) {
        showStatus("Member ID is required before importing a private key.", 5000);
        return;
    }

    dom.importIdentityBtn.disabled = true;
    try {
        const identity = await prepareLocalIdentityFromPrivateKey(
            privateKeyArmored,
            memberId,
            displayName,
            passphrase
        );
        saveLocalIdentity(identity);
        markTrustVerified(getLocalIdentityProjection());
        syncIdentityInputs();
        renderAll();
        showStatus("Local identity imported for this browser session.", 5000);
    } catch (error) {
        showStatus(`Identity import failed: ${error.message}`, 7000);
    } finally {
        dom.importIdentityBtn.disabled = false;
    }
}

async function addDraftMember() {
    const memberId = dom.peerMemberIdInput.value;
    const displayName = dom.peerDisplayNameInput.value;
    const publicKeyArmored = dom.peerPublicKeyInput.value;

    dom.addPeerBtn.disabled = true;
    try {
        const record = await derivePublicRecordFromKey(publicKeyArmored, memberId, displayName);
        const observation = observeTrustRecord(record);
        saveTrustStore();

        state.draftMembers = state.draftMembers.filter((member) => member.member_id !== record.member_id);
        state.draftMembers.push(record);
        saveDraftMembers();

        dom.peerMemberIdInput.value = "";
        dom.peerDisplayNameInput.value = "";
        dom.peerPublicKeyInput.value = "";

        renderAll();
        if (observation === "changed") {
            showStatus(
                `Added ${record.member_id} to the draft roster, but the key changed from what this browser previously knew.`,
                7000
            );
        } else {
            showStatus(`Added ${record.member_id} to the draft roster (${observation}).`, 5000);
        }
    } catch (error) {
        showStatus(`Could not add member: ${error.message}`, 7000);
    } finally {
        dom.addPeerBtn.disabled = false;
    }
}

function verifyDraftMember(memberId) {
    const record = state.draftMembers.find((member) => member.member_id === memberId);
    if (!record) {
        return;
    }
    markTrustVerified(record);
    renderAll();
    showStatus(`Marked ${memberId} verified in the local trust store.`, 5000);
}

function verifyActiveMember(memberId) {
    const activeEpoch = getActiveEpoch();
    if (!activeEpoch) {
        return;
    }
    const record = activeEpoch.members.find((member) => member.member_id === memberId);
    if (!record) {
        return;
    }
    if (getTrustStatusForRecord(record) === "changed") {
        showStatus("Key changes cannot be accepted inside an active alpha room. Create a new room.", 7000);
        return;
    }
    markTrustVerified(record);
    renderAll();
    showStatus(`Marked ${memberId} verified in the local trust store.`, 5000);
}

async function bootstrapRoom() {
    const activeEpoch = getActiveEpoch();
    if (activeEpoch) {
        showStatus("This room already has an active roster.", 5000);
        return;
    }

    if (!state.localIdentity) {
        showStatus("Generate or import the local identity before locking the roster.", 7000);
        return;
    }

    const localProjection = getLocalIdentityProjection();
    const draftMembers = state.draftMembers.filter(
        (member) => member.member_id !== localProjection.member_id
    );
    const rosterMembers = [localProjection].concat(draftMembers);

    if (!rosterMembers.length) {
        showStatus("Roster must contain at least one member.", 5000);
        return;
    }

    const unverifiedMembers = draftMembers.filter(
        (member) => getTrustStatusForRecord(member) !== "verified"
    );
    if (unverifiedMembers.length) {
        showStatus(
            `Verify every draft member before locking the roster: ${unverifiedMembers.map((member) => member.member_id).join(", ")}.`,
            8000
        );
        return;
    }

    dom.lockRosterBtn.disabled = true;
    try {
        const response = await fetch(`/chat/room/${roomId}/state/bootstrap`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                creator_member_id: localProjection.member_id,
                members: rosterMembers,
            }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Room bootstrap failed");
        }

        state.roomState = data;
        state.draftMembers = [];
        saveDraftMembers();
        observeActiveRoster();
        renderAll();
        await fetchMessages();
        showStatus("Locked epoch 1. Future messages will be signed and encrypted to the full roster.", 7000);
    } catch (error) {
        showStatus(`Could not lock the roster: ${error.message}`, 8000);
    } finally {
        dom.lockRosterBtn.disabled = false;
    }
}

function observeActiveRoster() {
    const activeEpoch = getActiveEpoch();
    if (!activeEpoch) {
        return;
    }

    let changed = false;
    activeEpoch.members.forEach((member) => {
        const status = observeTrustRecord(member);
        if (status === "new" || status === "known" || status === "verified") {
            changed = true;
        }
    });

    if (changed) {
        saveTrustStore();
    }

    state.keyCache = null;
    state.keyCacheHash = null;
}

async function fetchRoomState() {
    try {
        const response = await fetch(`/chat/room/${roomId}/state`);
        if (!response.ok) {
            throw new Error("Could not load room state");
        }

        state.roomState = await response.json();
        observeActiveRoster();
        renderAll();
    } catch (error) {
        showStatus(`Room state error: ${error.message}`, 6000);
    }
}

function formatTimestamp(timestamp) {
    if (!timestamp) {
        return "";
    }
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
        return timestamp;
    }
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

async function decryptAndValidateMessage(record) {
    const activeEpoch = getActiveEpoch();
    const fallbackSender =
        record.sender_display_name ||
        record.username ||
        record.sender_member_id ||
        "Unknown";

    if (!activeEpoch) {
        return {
            accepted: false,
            senderDisplayName: fallbackSender,
            text: "[Room has not been bootstrapped yet.]",
            note: "",
        };
    }

    const localMember = getLocalRosterMember();
    if (!state.localIdentity || !localMember) {
        return {
            accepted: false,
            senderDisplayName: fallbackSender,
            text: "[Configure the matching local identity to decrypt room messages.]",
            note: "",
        };
    }

    let privateKey;
    try {
        privateKey = await getUnlockedPrivateKey();
    } catch (error) {
        return {
            accepted: false,
            senderDisplayName: fallbackSender,
            text: `[${error.message}]`,
            note: "",
        };
    }

    let message;
    try {
        message = await openpgp.readMessage({
            armoredMessage: record.armored_message || record.message,
        });
    } catch (error) {
        return {
            accepted: false,
            senderDisplayName: fallbackSender,
            text: `[Unreadable armored message: ${error.message}]`,
            note: "",
        };
    }

    const packetKeyIds = message.getEncryptionKeyIDs().map((keyId) => keyId.toHex().toUpperCase());
    const anonymousRecipients = packetKeyIds.some((keyId) => /^0+$/.test(keyId));

    let decryptedData = "";
    let signatures = [];
    let signatureKeyId = null;
    let signatureOk = false;
    let decryptError = null;

    try {
        const verificationKeys = Object.values(await ensureRoomKeyCache());
        const result = await openpgp.decrypt({
            message,
            decryptionKeys: privateKey,
            verificationKeys,
            expectSigned: true,
            format: "utf8",
        });
        decryptedData = result.data;
        signatures = result.signatures || [];
        if (signatures.length > 0) {
            signatureKeyId = signatures[0].keyID ? signatures[0].keyID.toHex().toUpperCase() : null;
            await Promise.all(signatures.map((signature) => signature.verified));
            signatureOk = true;
        }
    } catch (error) {
        decryptError = error.message || "decryption failed";
    }

    if (decryptError) {
        return {
            accepted: false,
            senderDisplayName: fallbackSender,
            text: `[Rejected message: ${decryptError}]`,
            note: "",
        };
    }

    let payload = null;
    let parseError = null;
    try {
        payload = JSON.parse(decryptedData);
    } catch (error) {
        payload = {};
        parseError = error.message;
    }

    const expectedFingerprints = getExpectedRecipientFingerprints(activeEpoch);
    const expectedKeyIds = getExpectedRecipientKeyIds(activeEpoch);
    const senderMember = activeEpoch.members.find((member) => member.member_id === payload.sender_member_id);

    const errors = [];

    if (payload.type && payload.type !== ROOM_MODE) {
        errors.push("message type mismatch");
    }
    if (payload.room_id !== roomId) {
        errors.push("room_id mismatch");
    }
    if (Number(payload.epoch) !== Number(activeEpoch.epoch)) {
        errors.push("epoch mismatch");
    }
    if (String(payload.roster_hash || "").toUpperCase() !== String(activeEpoch.roster_hash || "").toUpperCase()) {
        errors.push("roster hash mismatch");
    }
    if (!senderMember) {
        errors.push("sender is not part of the roster");
    }
    if (
        senderMember &&
        String(payload.sender_signing_fingerprint || "").toUpperCase() !==
            senderMember.signing_fingerprint.toUpperCase()
    ) {
        errors.push("sender signing fingerprint mismatch");
    }
    if (
        senderMember &&
        signatureKeyId &&
        signatureKeyId !== senderMember.signing_key_id.toUpperCase()
    ) {
        errors.push("signature key id does not match the sender roster entry");
    }
    if (!packetKeyIds.includes(localMember.encryption_key_id.toUpperCase())) {
        errors.push("message was not encrypted to the local recipient");
    }
    if (anonymousRecipients) {
        errors.push("anonymous recipients are forbidden");
    }
    if (!arraysEqualAsSets(packetKeyIds, expectedKeyIds)) {
        errors.push("packet recipient key ids do not match the room roster");
    }
    if (
        !arraysEqualAsSets(
            payload.recipient_encryption_fingerprints || [],
            expectedFingerprints
        )
    ) {
        errors.push("recipient set does not match the room roster");
    }
    if (
        Array.isArray(payload.intended_recipient_fingerprints) &&
        payload.intended_recipient_fingerprints.length > 0 &&
        !arraysEqualAsSets(payload.intended_recipient_fingerprints, expectedFingerprints)
    ) {
        errors.push("intended recipient fingerprints do not match the room roster");
    }
    if (parseError) {
        errors.push(`message payload parse failed: ${parseError}`);
    }
    if (!signatureOk) {
        errors.push("message signature verification failed");
    }
    if (typeof payload.text !== "string") {
        errors.push("message text missing from payload");
    }
    if (
        record.sender_member_id &&
        payload.sender_member_id &&
        record.sender_member_id !== payload.sender_member_id
    ) {
        errors.push("outer sender metadata mismatch");
    }

    if (errors.length) {
        return {
            accepted: false,
            senderDisplayName: senderMember ? senderMember.display_name : fallbackSender,
            text: `[Rejected message: ${errors[0]}]`,
            note: errors.slice(1).join(" | "),
        };
    }

    const senderTrustStatus = senderMember ? getTrustStatusForRecord(senderMember) : "new";
    let note = "Pending local verification";
    if (senderTrustStatus === "verified") {
        note = "Verified locally";
    } else if (senderTrustStatus === "changed") {
        note = "Key changed locally";
    }

    return {
        accepted: true,
        senderDisplayName: senderMember ? senderMember.display_name : fallbackSender,
        text: payload.text,
        note,
    };
}

function scrollToBottom() {
    dom.messagesContainer.scrollTop = dom.messagesContainer.scrollHeight;
}

async function renderMessages(messages) {
    dom.messagesContainer.replaceChildren();

    if (!messages.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.innerHTML = "<h2>Room Messages</h2><p>No room messages yet.</p>";
        dom.messagesContainer.appendChild(empty);
        return;
    }

    for (const record of messages) {
        const resolved = await decryptAndValidateMessage(record);

        const wrapper = document.createElement("div");
        wrapper.className = `message${record.is_mine ? " mine" : ""}`;

        const header = document.createElement("div");
        header.className = "message-header";

        const title = document.createElement("div");
        title.className = "message-title";

        const sender = document.createElement("span");
        sender.className = "message-sender";
        sender.textContent = resolved.senderDisplayName;
        title.appendChild(sender);

        title.appendChild(
            createBadge(resolved.accepted ? "Accepted" : "Rejected", resolved.accepted ? "verified" : "changed")
        );

        if (record.is_mine) {
            title.appendChild(createBadge("You", "local"));
        }

        header.appendChild(title);

        const timestamp = document.createElement("div");
        timestamp.className = "message-meta";
        timestamp.textContent = formatTimestamp(record.timestamp);
        header.appendChild(timestamp);

        wrapper.appendChild(header);

        const body = document.createElement("div");
        body.className = `message-body${resolved.accepted ? "" : " rejected"}`;
        body.textContent = escapeForText(resolved.text);
        wrapper.appendChild(body);

        if (resolved.note) {
            const note = document.createElement("div");
            note.className = "message-note";
            note.textContent = resolved.note;
            wrapper.appendChild(note);
        }

        dom.messagesContainer.appendChild(wrapper);
    }

    scrollToBottom();
}

async function fetchMessages() {
    try {
        const response = await fetch(`/chat/room/${roomId}/messages`);
        if (!response.ok) {
            throw new Error("Could not load room messages");
        }

        const data = await response.json();
        dom.userCount.textContent = `Sessions: ${data.user_count}`;
        await renderMessages(data.messages || []);
    } catch (error) {
        showStatus(`Message sync error: ${error.message}`, 6000);
    }
}

async function sendMessage() {
    const readiness = getSendReadiness();
    if (!readiness.ready) {
        showStatus(readiness.message, 7000);
        return;
    }

    const text = String(dom.messageInput.value || "").trim();
    if (!text) {
        return;
    }
    if (text.length > maxMessageLength) {
        showStatus(`Message too long. Keep it under ${maxMessageLength} characters.`, 6000);
        return;
    }

    const activeEpoch = getActiveEpoch();
    const localMember = getLocalRosterMember();

    dom.sendBtn.disabled = true;
    try {
        const privateKey = await getUnlockedPrivateKey();
        const roomKeyMap = await ensureRoomKeyCache();
        const encryptionKeys = activeEpoch.members.map((member) => roomKeyMap[member.member_id]);
        const expectedFingerprints = normalizeUpperSet(
            activeEpoch.members.map((member) => member.encryption_fingerprint)
        );
        const expectedKeyIds = normalizeUpperSet(
            activeEpoch.members.map((member) => member.encryption_key_id)
        );

        const payload = {
            type: ROOM_MODE,
            room_id: roomId,
            epoch: activeEpoch.epoch,
            sender_member_id: localMember.member_id,
            sender_signing_fingerprint: localMember.signing_fingerprint,
            roster_hash: activeEpoch.roster_hash,
            recipient_encryption_fingerprints: expectedFingerprints,
            intended_recipient_fingerprints: expectedFingerprints,
            sent_at: new Date().toISOString(),
            text,
        };

        const armoredMessage = await openpgp.encrypt({
            message: await openpgp.createMessage({
                text: JSON.stringify(payload),
            }),
            encryptionKeys,
            signingKeys: privateKey,
            format: "armored",
            wildcard: false,
        });

        const response = await fetch(`/chat/room/${roomId}/messages`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                envelope_type: ROOM_MODE,
                room_id: roomId,
                epoch: activeEpoch.epoch,
                sender_member_id: localMember.member_id,
                sender_signing_fingerprint: localMember.signing_fingerprint,
                roster_hash: activeEpoch.roster_hash,
                recipient_encryption_fingerprints: expectedFingerprints,
                intended_recipient_fingerprints: expectedFingerprints,
                recipient_encryption_key_ids: expectedKeyIds,
                armored_message: armoredMessage,
            }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Message send failed");
        }

        dom.messageInput.value = "";
        await fetchMessages();
        showStatus("Signed and encrypted message delivered to the full roster.", 4000);
    } catch (error) {
        showStatus(`Send failed: ${error.message}`, 8000);
    } finally {
        updateComposerState();
    }
}

function acceptSecurityWarning() {
    state.securityWarningAccepted = true;
    sessionStorage.setItem(STORAGE_KEYS.warningAccepted, "true");
    dom.securityWarning.classList.remove("is-visible");
    updateComposerState();
}

function showSecurityWarning() {
    if (!state.securityWarningAccepted) {
        dom.securityWarning.classList.add("is-visible");
    }
}

async function copyPublicKey() {
    if (!state.localIdentity || !state.localIdentity.public_key_armored) {
        showStatus("No local public key is available yet.", 4000);
        return;
    }

    try {
        await navigator.clipboard.writeText(state.localIdentity.public_key_armored);
        showStatus("Copied the local public key to the clipboard.", 4000);
    } catch (error) {
        showStatus("Clipboard access failed. Copy the public key manually from the field.", 5000);
    }
}

async function downloadPrivateKey() {
    if (!state.localIdentity || !state.localIdentity.private_key_armored) {
        showStatus("No local private key is available yet.", 5000);
        return;
    }

    const memberId = String(state.localIdentity.member_id || "identity")
        .replace(/[^A-Za-z0-9._-]+/g, "-")
        .replace(/^-+|-+$/g, "") || "identity";
    const blob = new Blob([state.localIdentity.private_key_armored], {
        type: "application/pgp-keys",
    });
    const downloadUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl;
    anchor.download = `opsechat-${memberId}-private-key.asc`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(downloadUrl);

    saveIdentityBackup({
        member_id: state.localIdentity.member_id,
        signing_fingerprint: state.localIdentity.signing_fingerprint,
        encryption_fingerprint: state.localIdentity.encryption_fingerprint,
        downloaded_at: new Date().toISOString(),
    });
    renderAll();
    showStatus("Downloaded the armored private key. Store it securely outside this browser session.", 7000);
}

function clearLocalIdentity() {
    if (!state.localIdentity) {
        showStatus("No local identity is loaded.", 4000);
        return;
    }

    const confirmed = window.confirm(
        "Clear the local identity from this browser session? You will need the private-key backup to restore it."
    );
    if (!confirmed) {
        return;
    }

    clearLocalIdentityState();
    dom.privateKeyInput.value = "";
    dom.publicKeyOutput.value = "";
    dom.identityPassphraseInput.value = "";
    renderAll();
    showStatus("Cleared the local identity from this browser session.", 5000);
}

async function refreshLoop() {
    await fetchRoomState();
    await fetchMessages();
}

function wireEvents() {
    dom.acceptSecurityWarningBtn.addEventListener("click", acceptSecurityWarning);
    dom.addPeerBtn.addEventListener("click", addDraftMember);
    dom.clearIdentityBtn.addEventListener("click", clearLocalIdentity);
    dom.copyPublicKeyBtn.addEventListener("click", copyPublicKey);
    dom.downloadPrivateKeyBtn.addEventListener("click", downloadPrivateKey);
    dom.generateIdentityBtn.addEventListener("click", generateLocalIdentity);
    dom.importIdentityBtn.addEventListener("click", importLocalIdentity);
    dom.lockRosterBtn.addEventListener("click", bootstrapRoom);
    dom.sendBtn.addEventListener("click", sendMessage);

    dom.messageInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            sendMessage();
        }
    });

    dom.draftRosterList.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
            return;
        }
        const memberId = target.dataset.memberId;
        if (!memberId) {
            return;
        }
        if (target.dataset.action === "verify-draft") {
            verifyDraftMember(memberId);
        }
        if (target.dataset.action === "remove-draft") {
            removeDraftMember(memberId);
            renderAll();
            showStatus(`Removed ${memberId} from the draft roster.`, 4000);
        }
    });

    dom.rosterList.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
            return;
        }
        const memberId = target.dataset.memberId;
        if (!memberId) {
            return;
        }
        if (target.dataset.action === "verify-active") {
            verifyActiveMember(memberId);
        }
    });

    window.addEventListener("beforeunload", () => {
        if (state.pollInterval) {
            clearInterval(state.pollInterval);
        }
    });
}

async function init() {
    prepopulateIdentityInputs();
    renderAll();
    showSecurityWarning();
    await refreshLoop();
    state.pollInterval = setInterval(refreshLoop, 3000);
}

wireEvents();
init();
