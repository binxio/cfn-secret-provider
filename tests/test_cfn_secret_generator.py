import sys
import uuid
import cfn_secret_generator


class Event(dict):

    def __init__(self, request_type, name, physical_resource_id=None):
        self.update({
            'RequestType': 'Create',
            'ResponseURL': 'http://pre-signed-S3-url-for-response',
            'StackId': 'arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid',
            'RequestId': 'request-%s' % uuid.uuid4(),
            'ResourceType': 'Custom::SecretGenerator',
            'LogicalResourceId': 'MySecret',
            'ResourceProperties': {
                'Name': name
            }})
        if physical_resource_id is not None:
            self['PhysicalResourceId'] = physical_resource_id


def test_create():
    # create a test parameter
    name = '/test/parameter-%s' % uuid.uuid4()
    event = Event('Create', name)
    response = cfn_secret_generator.create_secret(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    assert 'Data' in response and 'Secret' in response['Data']
    physical_resource_id = response['PhysicalResourceId']

    # delete the parameters
    event = Event('Delete', name, physical_resource_id)
    response = cfn_secret_generator.delete_secret(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_prevent_duplicate_create():
    # prevent duplicate create
    name = '/test/parameter-%s' % uuid.uuid4()
    event = Event('Create', name)
    response = cfn_secret_generator.create_secret(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    event = Event('Create', name)
    response = cfn_secret_generator.create_secret(event, {})
    assert response['Status'] == 'FAILED', response['Reason']


def test_update_name():
    # update parameter name
    name = '/test/parameter-%s' % uuid.uuid4()
    event = Event('Create', name)
    response = cfn_secret_generator.create_secret(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']

    name_2 = '%s-2' % name
    event = Event('Update', name_2, physical_resource_id)
    response = cfn_secret_generator.update_secret(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    assert 'Data' in response and 'Secret' in response['Data']

    physical_resource_id_2 = response['PhysicalResourceId']
    assert physical_resource_id != physical_resource_id_2

    # delete the parameters
    event = Event('Delete', name, physical_resource_id)
    response = cfn_secret_generator.delete_secret(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    event = Event('Delete', name, physical_resource_id_2)
    response = cfn_secret_generator.delete_secret(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_prevent_duplicate_through_update():
    # update parameter name
    name = '/test/parameter-%s' % uuid.uuid4()
    event = Event('Create', name)
    response = cfn_secret_generator.create_secret(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    physical_resource_id = response['PhysicalResourceId']

    name_2 = '%s-2' % name
    event = Event('Create', name_2)
    response = cfn_secret_generator.update_secret(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id_2 = response['PhysicalResourceId']

    event = Event('Update', name, physical_resource_id_2)
    response = cfn_secret_generator.update_secret(event, {})
    assert response['Status'] == 'FAILED', response['Reason']

    # delete the parameters
    event = Event('Delete', name, physical_resource_id)
    response = cfn_secret_generator.delete_secret(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    event = Event('Delete', name, physical_resource_id_2)
    response = cfn_secret_generator.delete_secret(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
