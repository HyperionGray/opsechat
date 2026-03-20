(() => {
    "use strict";

    const STORAGE_KEY = "opsechat:key:primary";
    const EXPECTED_KEY_BYTES = 32;
    const FINGERPRINT_PREFIX_BYTES = 8;

    let activeKey = null;
    let activeKeyB64 = null;

    const keyStatus = document.getElementById("keyStatus");
    const keyFingerprint = document.getElementById("keyFingerprint");
    const importKeyInput = document.getElementById("importKeyInput");
    const exportKeyOutput = document.getElementById("exportKeyOutput");
    const generateKeyBtn = document.getElementById("generateKeyBtn");
    const importKeyBtn = document.getElementById("importKeyBtn");
    const copyKeyBtn = document.getElementById("copyKeyBtn");
    const deleteKeyBtn = document.getElementById("deleteKeyBtn");

    function setStatus(message, isError = false) {
        keyStatus.textContent = message;
        keyStatus.style.color = isError ? "#ff9a9a" : "#8ff58f";
    }

    function toBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = "";
        for (let i = 0; i < bytes.length; i += 1) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }

    function fromBase64(value) {
        const clean = value.replace(/\s+/g, "");
        const binary = atob(clean);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i += 1) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes;
    }

    async function importRawKey(rawBytes) {
        return window.crypto.subtle.importKey(
            "raw",
            rawBytes,
            { name: "AES-GCM", length: 256 },
            true,
            ["encrypt", "decrypt"]
        );
    }

    async function updateFingerprint(rawBytes) {
        const digest = await window.crypto.subtle.digest("SHA-256", rawBytes);
        const hex = Array.from(new Uint8Array(digest))
            .slice(0, FINGERPRINT_PREFIX_BYTES)
            .map((byte) => byte.toString(16).padStart(2, "0"))
            .join("");
        keyFingerprint.textContent = `Fingerprint: ${hex}`;
    }

    async function setActiveKey(rawBytes, sourceLabel) {
        activeKey = await importRawKey(rawBytes);
        activeKeyB64 = toBase64(rawBytes);
        exportKeyOutput.value = activeKeyB64;
        localStorage.setItem(STORAGE_KEY, activeKeyB64);
        await updateFingerprint(rawBytes);
        setStatus(`Key loaded from ${sourceLabel}.`);
    }

    function disableAll(message) {
        generateKeyBtn.disabled = true;
        importKeyBtn.disabled = true;
        copyKeyBtn.disabled = true;
        deleteKeyBtn.disabled = true;
        importKeyInput.disabled = true;
        exportKeyOutput.disabled = true;
        setStatus(message, true);
    }

    async function generateKey() {
        try {
            const key = await window.crypto.subtle.generateKey(
                { name: "AES-GCM", length: 256 },
                true,
                ["encrypt", "decrypt"]
            );
            const raw = await window.crypto.subtle.exportKey("raw", key);
            await setActiveKey(new Uint8Array(raw), "generation");
        } catch (error) {
            setStatus(`Failed to generate key: ${error.message}`, true);
        }
    }

    async function importKey() {
        try {
            const input = importKeyInput.value.trim();
            if (!input) {
                setStatus("Provide a base64 key before importing.", true);
                return;
            }

            const rawBytes = fromBase64(input);
            if (rawBytes.length !== EXPECTED_KEY_BYTES) {
                setStatus("Invalid key length. Expected 32 bytes (AES-256).", true);
                return;
            }

            await setActiveKey(rawBytes, "import");
            importKeyInput.value = "";
        } catch (error) {
            setStatus(`Failed to import key: ${error.message}`, true);
        }
    }

    async function copyKey() {
        if (!activeKeyB64) {
            setStatus("No key to copy.", true);
            return;
        }
        try {
            await navigator.clipboard.writeText(activeKeyB64);
            setStatus("Key copied to clipboard.");
        } catch (error) {
            setStatus(`Copy failed: ${error.message}`, true);
        }
    }

    function deleteKey() {
        activeKey = null;
        activeKeyB64 = null;
        localStorage.removeItem(STORAGE_KEY);
        exportKeyOutput.value = "";
        keyFingerprint.textContent = "Fingerprint: none";
        setStatus("Local key deleted.");
    }

    async function loadStoredKey() {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) {
            setStatus("No local key found. Generate or import one.");
            return;
        }

        try {
            const rawBytes = fromBase64(stored);
            if (rawBytes.length !== EXPECTED_KEY_BYTES) {
                throw new Error("Stored key has invalid length.");
            }
            await setActiveKey(rawBytes, "local storage");
        } catch (error) {
            localStorage.removeItem(STORAGE_KEY);
            exportKeyOutput.value = "";
            keyFingerprint.textContent = "Fingerprint: none";
            setStatus(`Stored key was invalid and was removed: ${error.message}`, true);
        }
    }

    function wireEvents() {
        generateKeyBtn.addEventListener("click", generateKey);
        importKeyBtn.addEventListener("click", importKey);
        copyKeyBtn.addEventListener("click", copyKey);
        deleteKeyBtn.addEventListener("click", deleteKey);
    }

    async function init() {
        if (!window.crypto || !window.crypto.subtle) {
            disableAll("Web Crypto API unavailable in this browser.");
            return;
        }
        wireEvents();
        await loadStoredKey();
    }

    init();
})();
