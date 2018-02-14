from cfn_rsakey_provider import RSAKeyProvider
from cryptography.hazmat.primitives.asymmetric import dsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from cryptography.hazmat.primitives import serialization as crypto_serialization


class DSAKeyProvider(RSAKeyProvider):

    def __init__(self):
        super(DSAKeyProvider, self).__init__()

    def get_key(self):
        response = self.ssm.get_parameter(Name=self.name_from_physical_resource_id(), WithDecryption=True)
        private_key = str(response['Parameter']['Value'])

        key = crypto_serialization.load_pem_private_key(
            private_key, password=None, backend=crypto_default_backend())

        public_key = key.public_key().public_bytes(
            crypto_serialization.Encoding.OpenSSH,
            crypto_serialization.PublicFormat.OpenSSH
        )
        return (private_key, public_key)

    def create_key(self):
        key = dsa.generate_private_key(
            backend=crypto_default_backend(),
            key_size=self.get('KeySize')
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


provider = DSAKeyProvider()


def handler(request, context):
    return provider.handle(request, context)
