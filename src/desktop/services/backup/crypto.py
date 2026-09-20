"""
TOYA ERP - Yedek Şifreleme (AES-256-GCM, parola tabanlı)

Biçim (`.enc`): MAGIC(8) | log2(N)(1) | salt(16) | nonce_öneki(8) | parça_boyutu(4) | parçalar…
Anahtar = scrypt(parola, salt). Her parça ayrı AES-GCM ile şifrelenir; nonce = önek + parça no,
ilişkili veri = (parça no, son_parça_mı). Böylece parçaların yeri değiştirilemez, dosya kesilemez, oynanamaz.
Yanlış parola ya da bozulma `DecryptError` verir; kısmi çıktı bırakılmaz.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"TOYAENC1"
SUFFIX = ".enc"
CHUNK = 1024 * 1024
LOG2_N = 15
_HEADER = struct.Struct(">8sB16s8sI")


class DecryptError(Exception):
    pass


def _key(password: str, salt: bytes, log2n: int) -> bytes:
    return Scrypt(salt=salt, length=32, n=1 << log2n, r=8, p=1).derive(password.encode("utf-8"))


def is_encrypted(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(8) == MAGIC
    except OSError:
        return False


def encrypt_file(src: Path, dest: Path, password: str, log2n: int = LOG2_N) -> None:
    if not password:
        raise ValueError("Şifreleme parolası boş olamaz.")
    salt, prefix = os.urandom(16), os.urandom(8)
    aes = AESGCM(_key(password, salt, log2n))
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    try:
        with open(src, "rb") as fin, open(part, "wb") as fout:
            fout.write(_HEADER.pack(MAGIC, log2n, salt, prefix, CHUNK))
            idx = 0
            block = fin.read(CHUNK)
            while True:
                nxt = fin.read(CHUNK)
                last = 0 if nxt else 1
                fout.write(aes.encrypt(prefix + struct.pack(">I", idx), block, struct.pack(">IB", idx, last)))
                if last:
                    break
                block, idx = nxt, idx + 1
        os.replace(part, dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def decrypt_file(src: Path, dest: Path, password: str) -> None:
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    try:
        with open(src, "rb") as fin:
            head = fin.read(_HEADER.size)
            if len(head) != _HEADER.size:
                raise DecryptError("Şifreli yedek başlığı eksik.")
            magic, log2n, salt, prefix, chunk = _HEADER.unpack(head)
            if magic != MAGIC or not (10 <= log2n <= 20) or not (1024 <= chunk <= 16 * 1024 * 1024):
                raise DecryptError("Bu bir TOYA şifreli yedeği değil.")
            aes = AESGCM(_key(password, salt, log2n))
            with open(part, "wb") as fout:
                idx = 0
                block = fin.read(chunk + 16)
                if not block:
                    raise DecryptError("Şifreli yedek boş/kesik.")
                while True:
                    nxt = fin.read(chunk + 16)
                    last = 0 if nxt else 1
                    try:
                        fout.write(aes.decrypt(prefix + struct.pack(">I", idx), block, struct.pack(">IB", idx, last)))
                    except InvalidTag:
                        raise DecryptError("Parola yanlış ya da yedek bozulmuş/değiştirilmiş.") from None
                    if last:
                        break
                    block, idx = nxt, idx + 1
        os.replace(part, dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
