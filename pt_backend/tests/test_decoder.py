from django.test import TestCase
from ..decoder import AESGCMDecryptor  # Sesuaikan path jika perlu

class AESGCMDecryptorTest(TestCase):
    def setUp(self):
        self.key = "12345678901234567890123456789012"
        self.encrypted_base64 = (
            "JavvSUy8sp/weWgshf8adiB3AWx/6+Od2hLrxlrjPI8soktzwt6yzukH6t8mZIakFcI+UOMQ1hg9UkqzEiS4he6vgWk="
        )
        self.expected_plaintext = "Pesan penting untuk didekripsi di Python"
        self.decryptor = AESGCMDecryptor(self.key)

    def test_decrypt_valid_encrypted_string(self):
        decrypted = self.decryptor.decrypt(self.encrypted_base64)
        self.assertEqual(decrypted, self.expected_plaintext)

    def test_decrypt_invalid_string(self):
        corrupted_input = "INVALID_STRING=="
        decrypted = self.decryptor.decrypt(corrupted_input)
        self.assertIsNone(decrypted)
