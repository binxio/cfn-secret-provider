import json
import logging
import os
import re

import boto3
from botocore.exceptions import ClientError
from cfn_resource_provider import ResourceProvider

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

request_schema = {
    "type": "object",
    "required": ["Name"],
    "properties": {
        "Name": {"type": "string", "minLength": 1, "pattern": "[a-zA-Z0-9_/]+",
                 "description": "the name of the secret"},
        "Description": {"type": "string", "default": "",
                        "description": "of the secret"},
        "KmsKeyId": {"type": "string", "default": "alias/aws/secretsmanager",
                     "description": "KMS key to use to encrypt the secret"},
        "SecretBinary": {"type": "string",
                         "description": "base64 encoded binary secret"},
        "SecretString": {
            "description": "secret string or json object or array to be converted to string",
            "anyOf": [
                {
                    "type": "string"
                },
                {
                    "type": "object"
                },
                {
                    "type": "array"
                }
            ]},
        "RecoveryWindowInDays": {
            "type": "integer", "default": 30,
            "description": "number of days a deleted secret can be restored",
            "minimum": 7, "maximum": 30
        },
        "ClientRequestToken": {"type": "string",
                               "description": "a unique identifier for the new version to ensure idempotency"},
        "NoEcho": {"type": "boolean", "default": True, "description": "the secret as output parameter"},
        "LambdaARN": {"type": "string", "description": "The Lambda used to rotate this secret"},
        "Interval": {"type": "integer", "minimum": 1, "maximum": 365,
                     "default": 30,
                     "description": "Number of days between secret rotations, max: 365"},
        "Tags": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["Key", "Value"],
                "properties": {
                    "Key": {"type": "string"},
                    "Value": {"type": "string"}
                }
            }
        }
    }
}


class SecretsManagerSecretProvider(ResourceProvider):

    def __init__(self):
        super(SecretsManagerSecretProvider, self).__init__()
        self._value = None
        self.request_schema = request_schema
        self.sm = boto3.client('secretsmanager')
        self.region = boto3.session.Session().region_name
        self.account_id = (boto3.client('sts')).get_caller_identity()['Account']

    def convert_property_types(self):
        try:
            if 'NoEcho' in self.properties and self.properties['NoEcho'] in ['true', 'false']:
                self.properties['NoEcho'] = (self.properties['NoEcho'] == 'true')
            if 'RecoveryWindowInDays' in self.properties:
                self.properties['RecoveryWindowInDays'] = int(self.properties['RecoveryWindowInDays'])
            if 'Interval' in self.properties:
                self.properties['Interval'] = int(self.properties['Interval'])
        except ValueError as e:
            log.error('failed to convert property types %s', e)

    def create_arguments(self):
        args = {
            'Name': self.get('Name'),
            'Description': self.get('Description'),
            'ClientRequestToken': self.get('ClientRequestToken', self.request_id),
            'KmsKeyId': self.get('KmsKeyId')
        }
        if self.get('Tags') is not None:
            args['Tags'] = self.get('Tags')
        if self.get('SecretBinary') is not None:
            args['SecretBinary'] = self.get('SecretBinary')
        if self.get('SecretString') is not None:
            s = self.get('SecretString')
            args['SecretString'] = s if isinstance(s, str) else json.dumps(s)

        return args

    def set_return_attributes(self, response):
        self.physical_resource_id = response['ARN']
        self.no_echo = self.get('NoEcho')

    def set_rotation_config(self):
        if self.get('LambdaARN') and self.get('Interval'):
            args = {
                'SecretId': self.get('Name'),
                'RotationLambdaARN': self.get('LambdaARN'),
                'RotationRules': {
                    'AutomaticallyAfterDays': self.get('Interval')
                }
            }
            self.sm.rotate_secret(**args)

    def create(self):
        try:
            args = self.create_arguments()
            response = self.sm.create_secret(**args)
            self.set_return_attributes(response)
            self.set_rotation_config()
        except ClientError as e:
            self.physical_resource_id = 'could-not-create'
            self.fail('{}'.format(e))

    def update(self):
        if self.get_old('Name', self.get('Name')) != self.get('Name'):
            self.fail('Cannot change the name of a secret')
            return

        try:
            args = self.create_arguments()
            args['SecretId'] = self.physical_resource_id
            del args['Name']
            if 'Tags' in args:
                del args['Tags']

            response = self.sm.update_secret(**args)
            self.set_return_attributes(response)

            self.set_rotation_config()

            if self.get_old('Tags', self.get('Tags')) != self.get('Tags'):
                if len(self.get_old('Tags')) > 0:
                    self.sm.untag_resource(SecretId=self.physical_resource_id,
                                           TagKeys=list(map(lambda t: t['Key'], self.get_old('Tags'))))
                self.sm.tag_resource(SecretId=self.physical_resource_id, Tags=self.get('Tags'))

        except ClientError as e:
            self.fail('{}'.format(e))

    def delete(self):
        if re.match(r'^arn:aws:secretsmanager:.*', self.physical_resource_id):
            try:
                self.sm.delete_secret(SecretId=self.physical_resource_id,
                                      RecoveryWindowInDays=self.get('RecoveryWindowInDays'))
                self.success('Secret with the name %s is scheduled for deletion' % self.get('Name'))
            except ClientError as e:
                if e.response["Error"]["Code"] != 'ResourceNotFoundException':
                    self.fail('{}'.format(e))
        else:
            self.success('Delete request for secret with the name {} is ignored'.format(self.get('Name')))


provider = SecretsManagerSecretProvider()


def handler(request, context):
    return provider.handle(request, context)
