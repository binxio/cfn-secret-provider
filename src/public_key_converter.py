import sys
import base64
import struct
import StringIO
from pyasn1.type import univ
from pyasn1.codec.der import encoder as der_encoder, decoder as der_decoder


def rsa_to_pem(rsa_public_key):
    """
    convert rsa key to PEM format. blatently stolen from https://gist.github.com/mahmoudimus/1654254
    """
    keyfields = rsa_public_key.split(None)
    if len(keyfields) < 2 or len(keyfields) > 3:
        raise ValueError('unknown rsa public key format, %s' % rsa_public_key)

    keytype = keyfields[0]
    keydata = keyfields[1]

    if keytype != 'ssh-rsa':
        raise ValueError('key is of type %s, expected ssh-rsa' % keytype)

    keydata = base64.b64decode(keydata)

    parts = []
    while keydata:
        # read the length of the data
        dlen = struct.unpack('>I', keydata[:4])[0]

        # read in <length> bytes
        data, keydata = keydata[4:dlen + 4], keydata[4 + dlen:]
        parts.append(data)

    e_val = eval('0x' + ''.join(['%02X' % struct.unpack('B', x)[0] for x in parts[1]]))
    n_val = eval('0x' + ''.join(['%02X' % struct.unpack('B', x)[0] for x in parts[2]]))

    bitstring = univ.Sequence()
    bitstring.setComponentByPosition(0, univ.Integer(n_val))
    bitstring.setComponentByPosition(1, univ.Integer(e_val))

    bitstring = der_encoder.encode(bitstring)

    bitstring = ''.join([('00000000' + bin(ord(x))[2:])[-8:] for x in list(bitstring)])

    bitstring = univ.BitString("'%s'B" % bitstring)

    pubkeyid = univ.Sequence()
    pubkeyid.setComponentByPosition(0, univ.ObjectIdentifier('1.2.840.113549.1.1.1'))  # == OID for rsaEncryption
    pubkeyid.setComponentByPosition(1, univ.Null(''))

    pubkey_seq = univ.Sequence()
    pubkey_seq.setComponentByPosition(0, pubkeyid)
    pubkey_seq.setComponentByPosition(1, bitstring)

    result = StringIO.StringIO()
    result.write("-----BEGIN PUBLIC KEY-----\n")
    base64.MAXBINSIZE = (64 // 4) * 3  # this actually doesn't matter, but it helped with comparing to openssl's output
    result.write(base64.encodestring(der_encoder.encode(pubkey_seq)))
    result.write('-----END PUBLIC KEY-----\n')
    return result.getvalue()
