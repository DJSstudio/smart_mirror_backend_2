from django.core.files.storage import FileSystemStorage

class EncryptedFileStorage(FileSystemStorage):
    """
    Placeholder for encrypted file storage.
    Currently behaves as normal storage.
    Add AES/GPG/LUKS-based encryption here if needed.
    """

    def _save(self, name, content):
        # TODO: Apply encryption before saving
        return super()._save(name, content)

    def open(self, name, mode='rb'):
        # TODO: Apply decryption on open
        return super().open(name, mode)
