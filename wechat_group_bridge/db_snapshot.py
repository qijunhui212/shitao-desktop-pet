# Read-only, committed-WAL snapshots; plaintext exists only in RAM.
from pathlib import Path
import sqlite3
import struct
import time
from .db_crypto import decrypt_page, verify_enc_key
ALLOWED = ('contact/contact.db', 'message/message_0.db')
def file_stamp(path):
    try:
        st=path.stat()
        return (st.st_size,st.st_mtime_ns)
    except FileNotFoundError:
        return (0,0)

def wal_checksum(data, initial=(0,0), byteorder='<'):
    if len(data)%8:
        raise ValueError('Invalid WAL checksum block.')
    s0,s1=initial
    for v0,v1 in struct.iter_unpack(byteorder+'II',data):
        s0=(s0+v0+s1)&0xffffffff
        s1=(s1+v1+s0)&0xffffffff
    return s0,s1

def committed_frames(wal):
    """Only apply a valid, committed WAL prefix, never torn/uncommitted data."""
    if len(wal)<32:
        return [],None
    magic,version,pagesize=struct.unpack('>III',wal[:12])
    if magic not in (0x377f0682,0x377f0683) or version!=3007000 or pagesize!=4096:
        raise RuntimeError('Unrecognized SQLite WAL header.')
    order='<' if magic==0x377f0682 else '>'
    checksum=wal_checksum(wal[:24],byteorder=order)
    if checksum!=struct.unpack('>II',wal[24:32]):
        raise RuntimeError('WAL header checksum mismatch.')
    frames=[]
    committed=0
    pages=None
    for offset in range(32,len(wal)-4119,4120):
        header=wal[offset:offset+24]
        page=wal[offset+24:offset+4120]
        pgno,db_pages=struct.unpack('>II',header[:8])
        if not pgno or pgno>1000000 or header[8:16]!=wal[16:24]:
            break
        check=wal_checksum(header[:8]+page,checksum,order)
        if check!=struct.unpack('>II',header[16:24]):
            break
        checksum=check
        frames.append((pgno,page))
        if db_pages:
            committed=len(frames)
            pages=db_pages
    return frames[:committed],pages

def snapshot(database,rel,keys):
    if rel not in ALLOWED:
        raise ValueError('Database outside the authorized scope.')
    path=database/rel
    walpath=Path(str(path)+'-wal')
    for attempt in range(4):
        stamp=(file_stamp(path),file_stamp(walpath))
        enc=path.read_bytes()
        wal=walpath.read_bytes() if walpath.exists() else b''
        if stamp==(file_stamp(path),file_stamp(walpath)):
            break
        time.sleep(.15)
    else:
        raise RuntimeError('Database changed during capture; retry after a quiet moment.')
    key=bytes.fromhex(keys[rel]['enc_key'])
    if len(enc)%4096 or not verify_enc_key(key,enc[:4096]):
        raise RuntimeError('Database key validation failed.')
    frames,committed_size=committed_frames(wal)
    size=committed_size*4096 if committed_size else len(enc)
    plain=bytearray(size)
    for offset in range(0,min(len(enc),size),4096):
        plain[offset:offset+4096]=decrypt_page(key,enc[offset:offset+4096],offset//4096+1)
    for pgno,page in frames:
        if pgno*4096<=size:
            offset=(pgno-1)*4096
            plain[offset:offset+4096]=decrypt_page(key,page,pgno)
    # The WAL has been applied. Force the private in-memory view into rollback
    # mode so SQLite never looks for a nonexistent disk WAL. Original is untouched.
    plain[18:20]=b'\x01\x01'
    conn=sqlite3.connect(':memory:')
    conn.deserialize(plain)
    conn.execute('PRAGMA query_only=ON')
    return conn,{'source_bytes':len(enc),'wal_committed_frames':len(frames),'stamp':stamp}
