from public_key_converter import rsa_to_pem
import subprocess
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend


def create_key():
    key = rsa.generate_private_key(
        backend=crypto_default_backend(),
        public_exponent=65537,
        key_size=2048
    )
    private_key = key.private_bytes(
        crypto_serialization.Encoding.PEM,
        crypto_serialization.PrivateFormat.PKCS8,
        crypto_serialization.NoEncryption())

    public_key = key.public_key().public_bytes(
        crypto_serialization.Encoding.OpenSSH,
        crypto_serialization.PublicFormat.OpenSSH
    )
    return (private_key, public_key)


def test_simple():
    private_key, public_key = create_key()
    result = rsa_to_pem(public_key)

    p = subprocess.Popen(["openssl", "rsa", "-inform", "PEM", "-pubout"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    out, err = p.communicate(private_key)
    public_key = out.decode()

    assert result == public_key
