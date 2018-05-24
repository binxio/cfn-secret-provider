import sys
import boto3
import uuid
from cfn_keypair_provider import KeyPairProvider
from secrets import handler


def test_defaults():
    request = Request('Create', 'abc')
    r = KeyPairProvider()
    r.set_request(request, {})
    assert r.is_valid_request()
    assert r.get('Name') == 'abc'
    assert r.get('PublicKeyMaterial') is not None

    request['ResourceProperties'] = {'Name': 'abc'}
    r.set_request(request, {})
    assert not r.is_valid_request(), 'PublicKeyMaterial is required'

    request['ResourceProperties'] = {'PublicKeyMaterial': 'abc'}
    r.set_request(request, {})
    assert not r.is_valid_request(), 'Name is required'


def test_key_name_from_physical_resource_id():
    request = Request('Update', 'abc', 'arn:aws:ec2:eu-central-1:245111612214:keypair/kb062b200-4b67-4eee-8933-44d76c0a199a')
    provider = KeyPairProvider()
    provider.set_request(request, {})
    assert provider.key_name_from_physical_resource_id() == 'kb062b200-4b67-4eee-8933-44d76c0a199a'

    request = Request('Update', 'abc', 'sdfasdfsdfsf')
    provider = KeyPairProvider()
    provider.set_request(request, {})
    assert provider.key_name_from_physical_resource_id() is None


def get_finger_print(name):
    ec2 = boto3.resource('ec2')
    key_pair = ec2.KeyPair(name)
    key_pair.load()
    return key_pair.key_fingerprint


def test_create_and_public():
    # create a test parameter
    provider = KeyPairProvider()
    name = 'k%s' % uuid.uuid4()
    request = Request('Create', name)
    response = provider.handle(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert provider.is_valid_cfn_response(), response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']

    assert 'Data' in response
    assert 'Arn' in response['Data']
    assert response['Data']['Arn'] == physical_resource_id

    finger_print_1 = get_finger_print(name)
    assert finger_print_1 is not None

    # update the material
    request = Request('Update', name, physical_resource_id, KeyPair().public_key_material)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    finger_print_2 = get_finger_print(name)
    assert finger_print_2 is not None
    assert finger_print_1 != finger_print_2

    # delete the parameters
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_request_duplicate_create():
    # prrequest duplicate create
    name = 'k%s' % uuid.uuid4()
    request = Request('Create', name)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    physical_resource_id = response['PhysicalResourceId']

    request = Request('Create', name)
    response = handler(request, {})
    assert response['Status'] == 'FAILED', response['Reason']

    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_update_name():
    # create a keypair
    name = 'k%s' % uuid.uuid4()
    request = Request('Create', name)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']

    # update keypair name
    name_2 = 'k2%s' % name
    request = Request('Update', name_2, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response

    physical_resource_id_2 = response['PhysicalResourceId']
    assert physical_resource_id != physical_resource_id_2

    # delete the keypairs
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    request = Request('Delete', name, physical_resource_id_2)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_request_duplicate_through_update():
    # update parameter name
    name = 'k%s' % uuid.uuid4()
    request = Request('Create', name)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    physical_resource_id = response['PhysicalResourceId']

    name_2 = 'k2%s' % name
    request = Request('Create', name_2)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id_2 = response['PhysicalResourceId']

    request = Request('Update', name, physical_resource_id_2)
    response = handler(request, {})
    assert response['Status'] == 'FAILED', response['Reason']

    # delete the parameters
    request = Request('Delete', name, physical_resource_id)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    request = Request('Delete', name, physical_resource_id_2)
    response = handler(request, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


class KeyPair(object):

    def __init__(self):
        from cryptography.hazmat.primitives import serialization as crypto_serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend as crypto_default_backend

        self.key = rsa.generate_private_key(
            backend=crypto_default_backend(),
            public_exponent=65537,
            key_size=2048
        )
        self.private_key = self.key.private_bytes(
            crypto_serialization.Encoding.PEM,
            crypto_serialization.PrivateFormat.PKCS8,
            crypto_serialization.NoEncryption()).decode('ascii')

        self.public_key = self.key.public_key().public_bytes(
            crypto_serialization.Encoding.OpenSSH,
            crypto_serialization.PublicFormat.OpenSSH
        ).decode('ascii')

    @property
    def public_key_material(self):
        return self.public_key


class Request(dict):

    def __init__(self, request_type, name, physical_resource_id=str(uuid.uuid4()),
                 public_key_material=KeyPair().public_key_material):
        self.update({
            'RequestType': request_type,
            'ResponseURL': 'https://httpbin.org/put',
            'StackId': 'arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid',
            'RequestId': 'request-%s' % uuid.uuid4(),
            'ResourceType': 'Custom::KeyPair',
            'LogicalResourceId': 'MyKey',
            'PhysicalResourceId': physical_resource_id,
            'ResourceProperties': {
                'Name': name,
                'PublicKeyMaterial': public_key_material
            }})
