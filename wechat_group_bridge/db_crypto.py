# Narrow read-only helpers adapted from the local wechat-cli-plus checkout.
import hashlib
import hmac as hmac_mod
import struct
from Crypto.Cipher import AES
import zstandard as zstd
PAGE_SZ = 4096
KEY_SZ = 32
SALT_SZ = 16
RESERVE_SZ = 80
SQLITE_HDR = b'SQLite format 3\x00'
_zstd_dctx = zstd.ZstdDecompressor()
def decrypt_page(enc_key, page_data, pgno):
    iv = page_data[PAGE_SZ - RESERVE_SZ: PAGE_SZ - RESERVE_SZ + 16]
    if pgno == 1:
        encrypted = page_data[SALT_SZ: PAGE_SZ - RESERVE_SZ]
        cipher = AES.new(enc_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted)
        return bytes(bytearray(SQLITE_HDR + decrypted + b'\x00' * RESERVE_SZ))
    else:
        encrypted = page_data[:PAGE_SZ - RESERVE_SZ]
        cipher = AES.new(enc_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted)
        return decrypted + b'\x00' * RESERVE_SZ

def verify_enc_key(enc_key, db_page1):
    """通过 HMAC-SHA1 (新版) 或 HMAC-SHA512 (旧版) 校验 page 1 验证 enc_key 是否正确。

    微信 3.9+ 使用 HMAC-SHA1，更早版本使用 HMAC-SHA512。
    """
    salt = db_page1[:SALT_SZ]
    mac_salt = bytes(b ^ 0x3A for b in salt)

    # 尝试 HMAC-SHA1 (新版微信 3.9+, 包括 4.1.x)
    try:
        mac_key = hashlib.pbkdf2_hmac("sha1", enc_key, mac_salt, 64000, dklen=KEY_SZ)
        hmac_data = db_page1[SALT_SZ: PAGE_SZ - 32]
        stored_hmac = db_page1[PAGE_SZ - 32: PAGE_SZ - 12]
        hm = hmac_mod.new(mac_key, hmac_data, hashlib.sha1)
        hm.update(struct.pack("<I", 1))
        if hm.digest()[:20] == stored_hmac:
            return True
    except Exception:
        pass

    # 回退到 HMAC-SHA512 (旧版微信)
    try:
        mac_key = hashlib.pbkdf2_hmac("sha512", enc_key, mac_salt, 2, dklen=KEY_SZ)
        hmac_data = db_page1[SALT_SZ: PAGE_SZ - 80 + 16]
        stored_hmac = db_page1[PAGE_SZ - 64: PAGE_SZ]
        hm = hmac_mod.new(mac_key, hmac_data, hashlib.sha512)
        hm.update(struct.pack("<I", 1))
        return hm.digest() == stored_hmac
    except Exception:
        return False

def decompress_content(content, ct):
    if ct and ct == 4 and isinstance(content, bytes):
        try:
            return _zstd_dctx.decompress(content).decode('utf-8', errors='replace')
        except Exception:
            return None
    if isinstance(content, bytes):
        try:
            return content.decode('utf-8', errors='replace')
        except Exception:
            return None
    return content
