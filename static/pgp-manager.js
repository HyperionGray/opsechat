// PGP Manager for opsechat
// Handles encryption, decryption, and key management

const PGPManager = (function() {
    'use strict';
    
    const STORAGE_KEYS = {
        PRIVATE_KEY: 'pgp_private_key',
        PUBLIC_KEYS: 'pgp_public_keys',
        PASSPHRASE: 'pgp_passphrase'
    };
    
    // Load private key from localStorage
    function getPrivateKey() {
        return localStorage.getItem(STORAGE_KEYS.PRIVATE_KEY);
    }
    
    // Save private key to localStorage
    function setPrivateKey(armoredKey) {
        localStorage.setItem(STORAGE_KEYS.PRIVATE_KEY, armoredKey);
    }
    
    // Load all public keys from localStorage
    function getPublicKeys() {
        const keys = localStorage.getItem(STORAGE_KEYS.PUBLIC_KEYS);
        return keys ? JSON.parse(keys) : {};
    }
    
    // Save public key for a user
    function addPublicKey(username, armoredKey) {
        const keys = getPublicKeys();
        keys[username] = armoredKey;
        localStorage.setItem(STORAGE_KEYS.PUBLIC_KEYS, JSON.stringify(keys));
    }
    
    // Remove public key for a user
    function removePublicKey(username) {
        const keys = getPublicKeys();
        delete keys[username];
        localStorage.setItem(STORAGE_KEYS.PUBLIC_KEYS, JSON.stringify(keys));
    }
    
    // Get passphrase (in-memory only for security)
    let cachedPassphrase = null;
    
    function setPassphrase(passphrase) {
        cachedPassphrase = passphrase;
    }
    
    function getPassphrase() {
        return cachedPassphrase;
    }
    
    // Clear private key
    function clearPrivateKey() {
        localStorage.removeItem(STORAGE_KEYS.PRIVATE_KEY);
        cachedPassphrase = null;
    }
    
    // Clear all public keys
    function clearAllPublicKeys() {
        localStorage.removeItem(STORAGE_KEYS.PUBLIC_KEYS);
    }
    
    // Check if message is PGP encrypted
    function isPGPMessage(text) {
        return text.includes('-----BEGIN PGP MESSAGE-----');
    }
    
    // Encrypt a message for all users with public keys
    async function encryptMessage(plaintext) {
        const publicKeys = getPublicKeys();
        const publicKeyList = Object.values(publicKeys);
        
        if (publicKeyList.length === 0) {
            // No public keys available, return plaintext
            return plaintext;
        }
        
        try {
            const publicKeyObjects = await Promise.all(
                publicKeyList.map(key => openpgp.readKey({ armoredKey: key }))
            );
            
            const encrypted = await openpgp.encrypt({
                message: await openpgp.createMessage({ text: plaintext }),
                encryptionKeys: publicKeyObjects
            });
            
            return encrypted;
        } catch (err) {
            console.error('Encryption error:', err);
            return plaintext; // Fallback to plaintext
        }
    }
    
    // Decrypt a message using the private key
    async function decryptMessage(ciphertext) {
        if (!isPGPMessage(ciphertext)) {
            return ciphertext; // Not encrypted, return as-is
        }
        
        const privateKeyArmored = getPrivateKey();
        if (!privateKeyArmored) {
            return '[Encrypted message - private key not configured]';
        }
        
        try {
            const privateKey = await openpgp.decryptKey({
                privateKey: await openpgp.readPrivateKey({ armoredKey: privateKeyArmored }),
                passphrase: getPassphrase() || ''
            });
            
            const message = await openpgp.readMessage({
                armoredMessage: ciphertext
            });
            
            const { data: decrypted } = await openpgp.decrypt({
                message,
                decryptionKeys: privateKey
            });
            
            return decrypted;
        } catch (err) {
            console.error('Decryption error:', err);
            return '[Failed to decrypt message]';
        }
    }
    
    // Check if PGP is enabled (has private key or public keys)
    function isEnabled() {
        return getPrivateKey() !== null || Object.keys(getPublicKeys()).length > 0;
    }
    
    // Check if encryption is possible (has public keys)
    function canEncrypt() {
        return Object.keys(getPublicKeys()).length > 0;
    }
    
    // Check if decryption is possible (has private key)
    function canDecrypt() {
        return getPrivateKey() !== null;
    }
    
    // Export public interface
    return {
        getPrivateKey,
        setPrivateKey,
        getPublicKeys,
        addPublicKey,
        removePublicKey,
        setPassphrase,
        clearPrivateKey,
        clearAllPublicKeys,
        isPGPMessage,
        encryptMessage,
        decryptMessage,
        isEnabled,
        canEncrypt,
        canDecrypt
    };
})();
