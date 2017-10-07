import boto3
import hashlib
import logging
import time
import string
import os
from random import choice
from botocore.exceptions import ClientError
from cfn_resource_provider import ResourceProvider
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend

log = logging.getLogger()

request_schema = {
    "type": "object",
    "required": ["Name"],
    "properties": {
        "Name": {"type": "string", "minLength": 1, "pattern": "[a-zA-Z0-9_/]+",
                 "description": "the name of the private key in the parameters store"},
        "Description": {"type": "string", "default": "",
                        "description": "the description of the key in the parameter store"},
        "ReturnSecret": {"type": "boolean",
                         "default": False,
                         "description": "return key as attribute 'Secret'"},
        "KeyAlias": {"type": "string",
                     "default": "alias/aws/ssm",
                     "description": "KMS key to use to encrypt the key"}
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

    @property
    def allow_overwrite(self):
        return self.physical_resource_id == self.arn

    @property
    def arn(self):
        return 'arn:aws:ssm:%s:%s:parameter/%s' % (self.region, self.account_id, self.get('Name'))

    def create_or_update_secret(self):
        try:
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
            self.ssm.put_parameter(Name=self.get('Name'), KeyId=self.get('KeyAlias'),
                                   Type='SecureString', Overwrite=self.allow_overwrite, Value=private_key)
            self.set_attribute('Arn', self.arn)
            self.set_attribute('PublicKey', public_key)
            if self.get('ReturnSecret'):
                self.set_attribute('Secret', private_key)

            self.physical_resource_id = self.arn
        except ClientError as e:
            self.physical_resource_id = 'could-not-create'
            self.fail(str(e))

    def create(self):
        self.create_or_update_secret()

    def update(self):
        self.create_or_update_secret()

    def delete(self):
        name = self.physical_resource_id.split('/', 1)
        if len(name) == 2:
            try:
                response = self.ssm.delete_parameter(Name=name[1])
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
