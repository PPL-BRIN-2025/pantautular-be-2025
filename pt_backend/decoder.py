from base64 import b64decode
from Crypto.Cipher import AES
from typing import Optional


class AESGCMDecryptor:
    def __init__(self, key: str):
        if len(key) != 32:
            raise ValueError("Key harus 32 karakter (256-bit) untuk AES-256-GCM.")
        self.key = key.encode('utf-8')

    def decrypt(self, encrypted_base64: str) -> Optional[str]:
        try:
            raw = b64decode(encrypted_base64)
            iv, tag, ciphertext = raw[:12], raw[12:28], raw[28:]

            cipher = AES.new(self.key, AES.MODE_GCM, nonce=iv)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)

            return plaintext.decode('utf-8')
        except Exception as e:
            print(f"[ERROR] Dekripsi gagal: {e}")
            return None
