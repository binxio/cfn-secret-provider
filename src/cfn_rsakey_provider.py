import boto3
import hashlib
import logging
from botocore.exceptions import ClientError
from cfn_resource_provider import ResourceProvider
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import ssm_parameter_name

log = logging.getLogger()

request_schema = {
    "type": "object",
    "required": ["Name"],
    "properties": {
        "Name": {"type": "string", "minLength": 1, "pattern": "[a-zA-Z0-9_/]+",
                 "description": "the name of the private key in the parameters store"},
        "KeySize": {"type": "integer", "default": 2048,
                    "description": "number of bits in the key"},
        "KeyFormat": {"type": "string",
                      "enum": ["PKCS8", "TraditionalOpenSSL"],
                      "default": "PKCS8",
                      "description": "encoding type of the private key"},
        "Description": {"type": "string", "default": "",
                        "description": "the description of the key in the parameter store"},
        "KeyAlias": {"type": "string",
                     "default": "alias/aws/ssm",
                     "description": "KMS key to use to encrypt the key"},
        "RefreshOnUpdate": {"type": "boolean", "default": False,
                            "description": "generate a new secret on update"},
        "Version": {"type": "string",  "description": "opaque string to force update"}
    }
}


class RSAKeyProvider(ResourceProvider):

    def __init__(self):
        super(RSAKeyProvider, self).__init__()
        self.request_schema = request_schema
        self.ssm = boto3.client('ssm')
        self.iam = boto3.client('iam')
        self.region = boto3.session.Session().region_name
        self.account_id = (boto3.client('sts')).get_caller_identity()['Account']

    def convert_property_types(self):
        self.heuristic_convert_property_types(self.properties)

    @property
    def allow_overwrite(self):
        return self.physical_resource_id == self.arn

    @property
    def arn(self):
        return ssm_parameter_name.to_arn(self.region, self.account_id, self.get('Name'))

    def name_from_physical_resource_id(self):
        return ssm_parameter_name.from_arn(self.physical_resource_id)

    @property
    def key_format(self):
        if self.get('KeyFormat', '') == 'TraditionalOpenSSL':
            return crypto_serialization.PrivateFormat.TraditionalOpenSSL
        else:
            return crypto_serialization.PrivateFormat.PKCS8

    def get_key(self):
        response = self.ssm.get_parameter(Name=self.name_from_physical_resource_id(), WithDecryption=True)
        private_key = response['Parameter']['Value'].encode('ascii')

        key = crypto_serialization.load_pem_private_key(
            private_key, password=None, backend=crypto_default_backend())

        private_key = key.private_bytes(
            crypto_serialization.Encoding.PEM,
            self.key_format,
            crypto_serialization.NoEncryption())

        public_key = key.public_key().public_bytes(
            crypto_serialization.Encoding.OpenSSH,
            crypto_serialization.PublicFormat.OpenSSH
        )
        return private_key.decode('ascii'), public_key.decode('ascii')

    def create_key(self):
        key = rsa.generate_private_key(
            backend=crypto_default_backend(),
            public_exponent=65537,
            key_size=self.get('KeySize')
        )
        private_key = key.private_bytes(
            crypto_serialization.Encoding.PEM,
            self.key_format,
            crypto_serialization.NoEncryption())

        public_key = key.public_key().public_bytes(
            crypto_serialization.Encoding.OpenSSH,
            crypto_serialization.PublicFormat.OpenSSH
        )
        return private_key.decode('ascii'), public_key.decode('ascii')

    def public_key_to_pem(self, private_key):
        key = crypto_serialization.load_pem_private_key(
            private_key.encode('ascii'), password=None, backend=crypto_default_backend())

        public_key = key.public_key().public_bytes(
            crypto_serialization.Encoding.PEM,
            crypto_serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return public_key.decode('ascii')

    def create_or_update_secret(self, overwrite=False, new_secret=True):
        try:
            if new_secret:
                private_key, public_key = self.create_key()
            else:
                private_key, public_key = self.get_key()

            kwargs = {
                'Name': self.get('Name'),
                'KeyId': self.get('KeyAlias'),
                'Type': 'SecureString',
                'Overwrite': overwrite,
                'Value': private_key
            }
            if self.get('Description') != '':
                kwargs['Description'] = self.get('Description')

            response = self.ssm.put_parameter(**kwargs)
            version = response['Version'] if 'Version' in response else 1

            self.set_attribute('Arn', self.arn)
            self.set_attribute('PublicKey', public_key)
            self.set_attribute('PublicKeyPEM', self.public_key_to_pem(private_key))
            self.set_attribute('Hash', hashlib.md5(public_key.encode('utf-8')).hexdigest())
            self.set_attribute('Version', version)

            self.physical_resource_id = self.arn
        except ClientError as e:
            self.physical_resource_id = 'could-not-create'
            self.fail(str(e))

    def create(self):
        self.create_or_update_secret(overwrite=False, new_secret=True)

    def update(self):
        self.create_or_update_secret(overwrite=self.allow_overwrite, new_secret=self.get('RefreshOnUpdate'))

    def delete(self):
        name = self.physical_resource_id.split('/', 1)
        if len(name) == 2:
            try:
                self.ssm.delete_parameter(Name=name[1])
            except ClientError as e:
                if e.response["Error"]["Code"] != 'ParameterNotFound':
                    return self.fail(str(e))

            self.success('System Parameter with the name %s is deleted' % name)
        else:
            self.success('System Parameter with the name %s is ignored' %
                         self.physical_resource_id)

provider = RSAKeyProvider()


def handler(request, context):
    return provider.handle(request, context)
