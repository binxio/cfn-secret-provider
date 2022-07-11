import re
import json
import uuid
import pytest
import boto3
from copy import copy
from botocore.exceptions import ClientError
from cfn_accesskey_provider import handler

iam = boto3.client("iam")
ssm = boto3.client("ssm")

created_users = []


def create_user(name):
    iam.create_user(UserName=name)
    created_users.append(name)


def delete_users():
    for name in created_users:
        keys = iam.list_access_keys(UserName=name)
        for key in keys["AccessKeyMetadata"]:
            iam.delete_access_key(UserName=name, AccessKeyId=key["AccessKeyId"])
        iam.delete_user(UserName=name)

        parameters = ssm.get_parameters_by_path(Path="/" + name)
        for parameter in parameters["Parameters"]:
            try:
                ssm.delete_parameter(Name=parameter["Name"])
            except ssm.exceptions.ParameterNotFound:
                pass

        try:
            ssm.delete_parameter(Name="/" + name)
        except ssm.exceptions.ParameterNotFound:
            pass


@pytest.fixture(scope="session", autouse=True)
def setup():
    yield
    delete_all_resources()
    delete_users()


def valid_deleted_state(request, response):
    data = response["Data"]
    properties = request["ResourceProperties"]
    name = properties["ParameterPath"]

    for n in ["/aws_access_key_id", "/aws_secret_access_key", "/smtp_password"]:
        try:
            parameter = ssm.get_parameter(Name=name + n)
            assert False, "parameter {}{} still exists".format(name, n)
        except ssm.exceptions.ParameterNotFound as e:
            pass

    keys = iam.list_access_keys(UserName=properties["UserName"])["AccessKeyMetadata"]
    assert len(keys) == 0, keys


def valid_state(request, response):
    data = response["Data"]
    properties = request["ResourceProperties"]
    name = properties["ParameterPath"]

    assert "PhysicalResourceId" in response
    access_key_id = response["PhysicalResourceId"]

    parameter = ssm.get_parameter(
        Name=name + "/aws_access_key_id", WithDecryption=True
    )["Parameter"]

    assert access_key_id == parameter["Value"]

    if "ReturnSecret" not in properties or not properties["ReturnSecret"]:
        assert "SecretAccessKey" not in data
    else:
        assert "SecretAccessKey" in data

    parameter = ssm.get_parameter(
        Name=name + "/aws_secret_access_key", WithDecryption=True
    )["Parameter"]
    if "SecretAccessKey" in data:
        assert data["SecretAccessKey"] == parameter["Value"]

    parameter = ssm.get_parameter(Name=name + "/smtp_password", WithDecryption=True)[
        "Parameter"
    ]
    if "SMTPPassword" in data:
        assert data["SMTPPassword"] == parameter["Value"]

    if "ReturnPassword" not in properties or not properties["ReturnPassword"]:
        assert "SMTPPassword" not in data
    else:
        assert "SMTPPassword" in data

    try:
        keys = iam.list_access_keys(UserName=properties["UserName"])[
            "AccessKeyMetadata"
        ]
        found = next(
            iter(filter(lambda x: x["AccessKeyId"] == access_key_id, keys)), None
        )
        assert found
    except ClientError as e:
        assert False, e.response

    assert "NoEcho" in response

    if "NoEcho" in properties:
        assert properties["NoEcho"] == response["NoEcho"]
    else:
        assert response["NoEcho"] == True

    assert "Hash" in response.get("Data", {})


objects = {}
cfn_deleted = {}


def fake_cfn(request, context):
    if request["RequestType"] == "Create":
        response = handler(request, context)
        if response["Status"] == "SUCCESS":
            physical_resource_id = response["PhysicalResourceId"]
            objects[physical_resource_id] = json.loads(json.dumps(request))

    if request["RequestType"] == "Delete":
        physical_resource_id = request["PhysicalResourceId"]
        response = handler(request, context)
        if physical_resource_id in objects:
            del objects[physical_resource_id]
        return response

    if request["RequestType"] == "Update":
        physical_resource_id = request["PhysicalResourceId"]
        exists = physical_resource_id in objects
        assert exists
        request["OldResourceProperties"] = json.loads(
            json.dumps(objects[physical_resource_id]["ResourceProperties"])
        )
        response = handler(request, context)
        if response["Status"] == "SUCCESS":
            if response["PhysicalResourceId"] != physical_resource_id:
                objects[response["PhysicalResourceId"]] = json.loads(
                    json.dumps(request)
                )
                # delete the old resource, if the physical resource id change
                delete_request = json.loads(json.dumps(objects[physical_resource_id]))
                delete_request["PhysicalResourceId"] = physical_resource_id
                delete_request["RequestType"] = "Delete"
                delete_response = handler(delete_request, context)
                assert delete_response["Status"] == "SUCCESS", delete_response["Reason"]
                cfn_deleted[physical_resource_id] = True

    return response


def test_create():
    name = "test-{}".format(uuid.uuid4())
    parameter_path = "/{0}/{0}".format(name)
    create_user(name)
    request = Request("Create", name, parameter_path)
    response = fake_cfn(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    valid_state(request, response)

    # update to obtain secret
    request = Request("Update", name, parameter_path, response["PhysicalResourceId"])
    request["ResourceProperties"]["ReturnSecret"] = True
    response = fake_cfn(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    valid_state(request, response)
    secret_access_key = response["Data"]["SecretAccessKey"]
    access_key_id = response["PhysicalResourceId"]

    # update to obtain password
    request = Request("Update", name, parameter_path, response["PhysicalResourceId"])
    request["ResourceProperties"]["ReturnPassword"] = True
    request["ResourceProperties"]["ReturnSecret"] = True
    request["ResourceProperties"]["NoEcho"] = False
    response = fake_cfn(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    valid_state(request, response)
    smtp_password = response["Data"]["SMTPPassword"]

    # change the region
    request = Request("Update", name, parameter_path, response["PhysicalResourceId"])
    request["ResourceProperties"]["SMTPRegion"] = "eu-west-1"
    request["ResourceProperties"]["ReturnPassword"] = True
    request["ResourceProperties"]["ReturnSecret"] = True
    new_response = fake_cfn(request, {})
    assert new_response["Status"] == "SUCCESS", response["Reason"]
    valid_state(request, new_response)

    new_smtp_password = new_response["Data"]["SMTPPassword"]
    assert response["PhysicalResourceId"] == new_response["PhysicalResourceId"]
    assert (
        response["Data"]["SecretAccessKey"] == new_response["Data"]["SecretAccessKey"]
    )
    assert smtp_password != new_smtp_password
    assert response["Data"]["Hash"] != new_response["Data"]["Hash"]

    # refresh the keys

    # refresh the keys
    request = Request("Update", name, parameter_path, response["PhysicalResourceId"])
    request["ResourceProperties"]["ReturnSecret"] = True
    request["ResourceProperties"]["ReturnPassword"] = True
    request["ResourceProperties"]["Serial"] = 2
    response = fake_cfn(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    valid_state(request, response)
    assert response["PhysicalResourceId"] != access_key_id
    assert response["Data"]["SecretAccessKey"] != secret_access_key
    secret_access_key = response["Data"]["SecretAccessKey"]
    access_key_id = response["PhysicalResourceId"]

    # change the user
    name2 = "test-{}".format(uuid.uuid4())
    create_user(name2)

    request["PhysicalResourceId"] = access_key_id
    request["ResourceProperties"]["UserName"] = name2
    response = fake_cfn(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    valid_state(request, response)
    assert response["PhysicalResourceId"] != access_key_id
    assert response["Data"]["SecretAccessKey"] != secret_access_key

    # get the latest stuff.
    secret_access_key = response["Data"]["SecretAccessKey"]
    access_key_id = response["PhysicalResourceId"]

    # change the user and parameter
    parameter_path_2 = "/{0}/new-{0}".format(name)
    request["PhysicalResourceId"] = access_key_id
    request["ResourceProperties"]["UserName"] = name
    request["ResourceProperties"]["ParameterPath"] = parameter_path_2
    response = fake_cfn(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    valid_state(request, response)
    assert "SMTPPassword" in response["Data"]
    assert "SecretAccessKey" in response["Data"]
    assert response["Data"]["SecretAccessKey"] != secret_access_key

    # get the latest stuff.
    secret_access_key = response["Data"]["SecretAccessKey"]
    access_key_id = response["PhysicalResourceId"]

    # inactivate the key
    request["PhysicalResourceId"] = access_key_id
    request["ResourceProperties"]["Status"] = "Inactive"
    response = fake_cfn(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert access_key_id == response["PhysicalResourceId"]
    valid_state(request, response)
    assert response["Data"]["SecretAccessKey"] == secret_access_key


def test_invalid_physical_resource_id():
    request = Request(
        "Delete", "bla", "/ok", "devapi-auth0rules-Auth0AccessKey-1F0NKYHR4YF7Y"
    )
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert response["Reason"] == "physical resource id is not an access key id."


def test_rename_parameter_path():
    name = "test-{}".format(uuid.uuid4())
    parameter_path = "/{0}/{0}".format(name)
    create_user(name)
    request = Request("Create", name, parameter_path)
    request["ReturnSecret"] = "true"
    request["ReturnPassword"] = "true"
    response = fake_cfn(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    valid_state(request, response)

    request["RequestType"] = "Update"
    request["PhysicalResourceId"] = response["PhysicalResourceId"]
    request["OldResourceProperties"] = copy(request["ResourceProperties"])
    request["ResourceProperties"]["ParameterPath"] = f"{parameter_path}-2"

    create_response = copy(response)
    response = fake_cfn(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    valid_state(request, response)
    assert create_response["Data"]["Hash"] == response["Data"]["Hash"]
    assert create_response["PhysicalResourceId"] == response["PhysicalResourceId"]
    response = ssm.get_parameters_by_path(
        WithDecryption=True, Path=f"{parameter_path}/", Recursive=True
    )
    assert not response["Parameters"]
    response = ssm.get_parameters_by_path(
        WithDecryption=True, Path=f"{parameter_path}-2/", Recursive=True
    )
    assert len(response["Parameters"]) == 3


def test_delete_non_existing_access_key():
    name = "/test-{}".format(uuid.uuid4())
    request = Request("Delete", "bla", name, "AAAAAAAAAAAAAAAAAA")
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert response["Reason"].startswith("no access key found under /")


def test_delete_lost_parameter_path():
    name = "test-{}".format(uuid.uuid4())
    parameter_path = "/{0}/{0}".format(name)
    create_user(name)

    request = Request("Create", name, parameter_path)
    response = fake_cfn(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    non_existing_path = "/test-{}".format(uuid.uuid4())
    request = Request("Delete", name, non_existing_path, response["PhysicalResourceId"])
    error_response = fake_cfn(request, {})
    assert error_response["Status"] == "SUCCESS", response["Reason"]
    assert error_response["Reason"].startswith("no access key found under /")

    request = Request("Delete", name, parameter_path, response["PhysicalResourceId"])
    response = fake_cfn(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert response["Reason"] == ""
    valid_deleted_state(request, response)


def delete_all_resources():
    # delete all objects
    print(json.dumps(objects, indent=2))
    print(json.dumps(cfn_deleted, indent=2))
    for physical_resource_id in list(objects.keys()):
        if physical_resource_id not in cfn_deleted:
            request = json.loads(json.dumps(objects[physical_resource_id]))
            request["PhysicalResourceId"] = physical_resource_id
            request["RequestType"] = "Delete"
            response = fake_cfn(request, {})
            assert response["Status"] == "SUCCESS", response["Reason"]
            valid_deleted_state(request, response)


class Request(dict):
    def __init__(
        self, request_type, user_name, parameter_path, physical_resource_id=None
    ):
        self.update(
            {
                "RequestType": request_type,
                "ResponseURL": "https://httpbin.org/put",
                "StackId": "arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid",
                "RequestId": "request-%s" % uuid.uuid4(),
                "ResourceType": "Custom::AccessKey",
                "LogicalResourceId": "MyAccessKey",
                "ResourceProperties": {
                    "UserName": user_name,
                    "ParameterPath": parameter_path,
                },
            }
        )
        self["PhysicalResourceId"] = (
            physical_resource_id
            if physical_resource_id is not None
            else str(uuid.uuid4())
        )
