import re
import boto3
import hashlib
import logging
import time
import string
import os
from random import choice
from botocore.exceptions import ClientError
from cfn_resource_provider import ResourceProvider

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


request_schema = {
    "type": "object",
            "required": ["Name", "PublicKeyMaterial"],
            "properties": {
                "Name": {"type": "string", "minLength": 1, "pattern": "[a-zA-Z0-9_/]+",
                         "description": "the name of the value in the parameters store"},
                "PublicKeyMaterial": {"type": "string",
                                      "description": "the description of the value in the parameter store"},
                "Version": {"type": "string",  "description": "opaque string to force update"}
            }
}


class KeyPairProvider(ResourceProvider):

    def __init__(self):
        super(KeyPairProvider, self).__init__()
        self._value = None
        self.request_schema = request_schema
        self.region = boto3.session.Session().region_name
        self.account_id = (boto3.client('sts')).get_caller_identity()['Account']
        self.ec2 = boto3.client('ec2')

    @property
    def allow_overwrite(self):
        return self.physical_resource_id == self.arn

    @property
    def arn(self):
        return 'arn:aws:ec2:%s:%s:keypair/%s' % (self.region, self.account_id, self.get('Name'))

    def key_name_from_physical_resource_id(self):
        """
        returns the key_name from the physical_resource_id as returned by self.arn, or None
        """
        arn_regexp = re.compile(r'arn:aws:ec2:(?P<region>[^:]*):(?P<account>[^:]*):keypair/(?P<name>.*)')
        m = re.match(arn_regexp, self.physical_resource_id)
        return m.group('name') if m is not None else None

    def import_keypair(self):
        try:
            self.ec2.import_key_pair(KeyName=self.get('Name'), PublicKeyMaterial=self.get('PublicKeyMaterial'))
            self.set_attribute('Arn', self.arn)
            self.physical_resource_id = self.arn
        except ClientError as e:
            self.physical_resource_id = 'could-not-create'
            self.fail(str(e))

        return self.status == 'SUCCESS'

    def delete_keypair(self, key_name):
        try:
            self.ec2.delete_key_pair(KeyName=key_name)
        except ClientError as e:
            self.fail(str(e))

        return self.status == 'SUCCESS'

    def create(self):
        self.import_keypair()

    def update(self):
        key_name = self.key_name_from_physical_resource_id()
        if key_name is None:
            self.fail('could not get the key name from the physical resource id, %s' % self.physical_resource_id)
            return

        if key_name != self.get('Name'):
            # rename of the key, just import as CFN will delete
            self.import_keypair()
        else:

            # update of the key, delete first
            if self.delete_keypair(key_name):
                self.import_keypair()

    def delete(self):
        key_name = self.key_name_from_physical_resource_id()
        if key_name is not None:
            try:
                self.delete_keypair(key_name)
            except ClientError as e:
                self.fail(str(e))
                return
            self.success('key pair with the name %s is deleted' % key_name)
        else:
            self.success('key pair with the name %s is ignored' % self.physical_resource_id)

provider = KeyPairProvider()


def handler(request, context):
    return provider.handle(request, context)
