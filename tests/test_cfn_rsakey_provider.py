import sys
import uuid
import boto3
import hashlib
from cfn_rsakey_provider import RSAKeyProvider
from secrets import handler

from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.backends import default_backend


def test_defaults():
    request = Request("Create", "abc")
    r = RSAKeyProvider()
    r.set_request(request, {})
    assert r.is_valid_request()
    assert r.get("KeyAlias") == "alias/aws/ssm"
    assert r.get("Description") == ""
    assert r.get("KeyFormat") == "PKCS8"


def test_create():
    # create a test parameter
    provider = RSAKeyProvider()
    name = "/test/parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    request["ResourceProperties"]["Description"] = "A ppretty private key"
    response = provider.handle(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert provider.is_valid_cfn_response(), response["Reason"]
    assert "PhysicalResourceId" in response
    physical_resource_id = response["PhysicalResourceId"]

    assert "Data" in response
    assert "Arn" in response["Data"]
    assert "PublicKey" in response["Data"]
    assert "Hash" in response["Data"]
    assert "Version" in response["Data"]
    assert response["Data"]["Arn"] == physical_resource_id
    assert (
        response["Data"]["Hash"]
        == hashlib.md5(response["Data"]["PublicKey"].encode("ascii")).hexdigest()
    )
    assert response["Data"]["Version"] == 1
    assert "ParameterName" in response["Data"]
    assert response["Data"]["ParameterName"] == name

    public_key = load_pem_public_key(
        response["Data"]["PublicKeyPEM"].encode("ascii"), backend=default_backend()
    )
    assert public_key.key_size == 2048

    request["RequestType"] = "Update"
    request["ResourceProperties"]["RefreshOnUpdate"] = True
    request["PhysicalResourceId"] = physical_resource_id
    response = provider.handle(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert (
        response["Data"]["Hash"]
        == hashlib.md5(response["Data"]["PublicKey"].encode("ascii")).hexdigest()
    )
    assert response["Data"]["Version"] == 2
    assert "ParameterName" in response["Data"]
    assert response["Data"]["ParameterName"] == name


# delete the parameters
    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_create_4096_key():
    # create a test parameter
    provider = RSAKeyProvider()
    name = "/test/parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    request["ResourceProperties"]["Description"] = "A large private key"
    request["ResourceProperties"]["KeySize"] = "4096"
    response = provider.handle(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert provider.is_valid_cfn_response(), response["Reason"]
    assert "PhysicalResourceId" in response
    physical_resource_id = response["PhysicalResourceId"]

    assert "Data" in response
    assert "Arn" in response["Data"]
    assert "PublicKey" in response["Data"]
    assert "PublicKeyPEM" in response["Data"]
    assert "Hash" in response["Data"]
    assert response["Data"]["Arn"] == physical_resource_id
    assert (
        response["Data"]["Hash"]
        == hashlib.md5(response["Data"]["PublicKey"].encode("ascii")).hexdigest()
    )

    public_key = load_pem_public_key(
        response["Data"]["PublicKeyPEM"].encode("ascii"), backend=default_backend()
    )
    assert public_key.key_size == 4096

    # delete the parameter
    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_create_traditional_openssl_key():
    # create a test parameter
    provider = RSAKeyProvider()
    name = "/test/parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    request["ResourceProperties"]["Description"] = "a key in openssl format"
    request["ResourceProperties"]["KeyFormat"] = "TraditionalOpenSSL"
    request["ResourceProperties"]["ReturnSecret"] = True
    response = provider.handle(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    physical_resource_id = response["PhysicalResourceId"]
    public_key = response["Data"]["PublicKeyPEM"]

    # check that it is in openssl format
    ssm = boto3.client("ssm")
    kp = ssm.get_parameter(Name=name, WithDecryption=True)
    private_key = kp["Parameter"]["Value"]
    assert private_key.split("\n")[0] == "-----BEGIN RSA PRIVATE KEY-----"

    # check it can reread the traditional form, and update back
    request["RequestType"] = "Update"
    request["ResourceProperties"]["KeyFormat"] = "PKCS8"
    request["PhysicalResourceId"] = physical_resource_id
    response = provider.handle(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert public_key == response["Data"]["PublicKeyPEM"]

    # check that it is in openssl format
    ssm = boto3.client("ssm")
    kp = ssm.get_parameter(Name=name, WithDecryption=True)
    private_key = kp["Parameter"]["Value"]
    assert private_key.split("\n")[0] == "-----BEGIN PRIVATE KEY-----"

    # delete the parameter
    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_type_convert():
    request = Request("Create", "abc")
    request["ResourceProperties"]["RefreshOnUpdate"] = "true"
    r = RSAKeyProvider()
    r.set_request(request, {})
    assert r.is_valid_request()
    assert isinstance(r.get("RefreshOnUpdate"), bool)


def test_request_duplicate_create():
    # prrequest duplicate create
    name = "/test/parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PublicKey" in response["Data"]
    physical_resource_id = response["PhysicalResourceId"]

    request = Request("Create", name)
    response = handler(request, {})
    assert response["Status"] == "FAILED", response["Reason"]

    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_update_name():
    # update parameter name
    name = "/test/parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PhysicalResourceId" in response
    physical_resource_id = response["PhysicalResourceId"]
    public_key_1 = response["Data"]["PublicKey"]

    name_2 = "%s-2" % name
    request = Request("Update", name_2, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PhysicalResourceId" in response
    assert "Data" in response and "Arn" in response["Data"]
    assert "ParameterName" in response["Data"]
    assert response["Data"]["ParameterName"] == name_2

    public_key_2 = response["Data"]["PublicKey"]

    physical_resource_id_2 = response["PhysicalResourceId"]
    assert physical_resource_id != physical_resource_id_2
    assert public_key_1 == public_key_2

    # delete the parameters
    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    request = Request("Delete", name, physical_resource_id_2)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_update_private_key():
    # create a keypair
    name = "k%s" % uuid.uuid4()
    request = Request("Create", name)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PhysicalResourceId" in response
    physical_resource_id = response["PhysicalResourceId"]
    public_key_material = response["Data"]["PublicKey"]
    secure_hash = response["Data"]["Hash"]

    # update keypair name
    name_2 = "k2%s" % name
    request = Request("Update", name_2, physical_resource_id)
    request["ResourceProperties"]["RefreshOnUpdate"] = True
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    physical_resource_id_2 = response["PhysicalResourceId"]
    assert physical_resource_id != physical_resource_id_2

    public_key_material_2 = response["Data"]["PublicKey"]
    assert public_key_material != public_key_material_2

    secure_hash_2 = response["Data"]["Hash"]
    assert secure_hash != secure_hash_2

    # delete the keypairs
    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    request = Request("Delete", name, physical_resource_id_2)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_request_duplicate_through_update():
    # update parameter name
    name = "/test/parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    physical_resource_id = response["PhysicalResourceId"]

    name_2 = "%s-2" % name
    request = Request("Create", name_2)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PhysicalResourceId" in response
    physical_resource_id_2 = response["PhysicalResourceId"]

    request = Request("Update", name, physical_resource_id_2)
    response = handler(request, {})
    assert response["Status"] == "FAILED", response["Reason"]

    # delete the parameters
    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    request = Request("Delete", name, physical_resource_id_2)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_create_no_return_secret():
    # create a test parameter
    name = "/test/parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PhysicalResourceId" in response
    physical_resource_id = response["PhysicalResourceId"]

    assert "Data" in response
    assert "Arn" in response["Data"]
    assert response["Data"]["Arn"] == physical_resource_id

    # delete the parameters
    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_no_echo():
    # create a test parameter
    name = "/test/parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    request["ResourceProperties"]["ReturnSecret"] = True
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    physical_resource_id = response["PhysicalResourceId"]
    request["PhysicalResourceId"] = physical_resource_id
    request["RequestType"] = "Update"
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    request["RequestType"] = "Delete"
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_unchanged_physical_resource_id():
    name = "k%s" % uuid.uuid4()
    request = Request("Create", name)
    request["ResourceProperties"]["ReturnSecret"] = True
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PhysicalResourceId" in response
    physical_resource_id = response["PhysicalResourceId"]

    old_style_physical_resource_id = physical_resource_id.split("/", 2)[0] + "//" + name
    request = Request("Update", name, old_style_physical_resource_id)
    request["ResourceProperties"]["RefreshOnUpdate"] = True
    request["ResourceProperties"]["ReturnSecret"] = True
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    assert old_style_physical_resource_id == response["PhysicalResourceId"]

    # delete secrets
    request = Request("Delete", name, old_style_physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


class Request(dict):
    def __init__(self, request_type, name, physical_resource_id=str(uuid.uuid4())):
        self.update(
            {
                "RequestType": request_type,
                "ResponseURL": "https://httpbin.org/put",
                "StackId": "arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid",
                "RequestId": "request-%s" % uuid.uuid4(),
                "ResourceType": "Custom::RSAKey",
                "LogicalResourceId": "MyKey",
                "PhysicalResourceId": physical_resource_id,
                "ResourceProperties": {"Name": name},
            }
        )
