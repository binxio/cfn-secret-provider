import boto3
import hashlib
import uuid
from base64 import b64encode, b64decode
from cfn_random_bytes_provider import RandomBytesProvider
from secrets import handler

kms = boto3.client("kms")

default_length = 8


def test_defaults():
    request = Request("Create", "abc")
    r = RandomBytesProvider()
    r.set_request(request, {})
    assert r.is_valid_request()
    assert not r.get("ReturnSecret")
    assert r.get("KeyAlias") == "alias/aws/ssm"
    assert r.get("Description") == ""
    assert r.get("Length") == default_length
    assert isinstance(r.get("NoEcho"), bool) and r.get("NoEcho")


def test_type_convert():
    request = Request("Create", "abc")
    request["ResourceProperties"]["Length"] = "62"
    request["ResourceProperties"]["ReturnSecret"] = "true"
    request["ResourceProperties"]["RefreshOnUpdate"] = "true"
    r = RandomBytesProvider()
    r.set_request(request, {})
    assert r.is_valid_request()
    assert r.get("Length") == 62
    assert r.get("ReturnSecret")

    request["ResourceProperties"]["Length"] = "fouteboole62"
    r = RandomBytesProvider()
    r.set_request(request, {})
    assert not r.is_valid_request()

    request["ResourceProperties"]["Length"] = u"62"
    request["ResourceProperties"]["ReturnSecret"] = u"true"
    r.set_request(request, {})
    assert r.is_valid_request()
    assert r.get("Length") == 62
    assert r.get("ReturnSecret")


def test_create():
    # create a test parameter
    name = "/test/1-parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    request["ResourceProperties"]["ReturnSecret"] = True
    request["ResourceProperties"]["Description"] = "A beautiful secret"
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PhysicalResourceId" in response
    physical_resource_id = response["PhysicalResourceId"]
    assert isinstance(physical_resource_id, str)

    assert "Data" in response
    assert "Secret" in response["Data"]
    assert len(b64decode(response["Data"]["Secret"])) == default_length
    assert "Arn" in response["Data"]
    assert "Hash" in response["Data"]
    assert "Version" in response["Data"]
    assert "NoEcho" in response
    assert response["Data"]["Arn"] == physical_resource_id
    assert (
        response["Data"]["Hash"]
        == hashlib.md5(response["Data"]["Secret"].encode("utf8")).hexdigest()
    )
    assert response["Data"]["Version"] == 1
    assert response["NoEcho"] == True
    assert "ParameterName" in response["Data"]
    assert response["Data"]["ParameterName"] == name


    # no update the key
    hash = response["Data"]["Hash"]
    request["RequestType"] = "Update"
    request["ResourceProperties"]["Length"] = "32"
    request["ResourceProperties"]["RefreshOnUpdate"] = False
    request["PhysicalResourceId"] = physical_resource_id
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert response["Data"]["Arn"] == physical_resource_id
    assert response["Data"]["Version"] == 2
    assert response["Data"]["Hash"] == hash
    assert len(b64decode(response["Data"]["Secret"])) == default_length

    # update the key
    hash = response["Data"]["Hash"]
    request["RequestType"] = "Update"
    request["ResourceProperties"]["RefreshOnUpdate"] = True
    request["ResourceProperties"]["Length"] = "32"
    request["PhysicalResourceId"] = physical_resource_id
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert response["Data"]["Arn"] == physical_resource_id
    assert response["Data"]["Version"] == 3
    assert response["Data"]["Hash"] != hash
    assert len(b64decode(response["Data"]["Secret"])) == 32

    response = handler(request, {})
    # delete the parameters
    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_request_duplicate_create():
    # prrequest duplicate create
    name = "/test/2-parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    physical_resource_id = response["PhysicalResourceId"]

    request = Request("Create", name)
    response = handler(request, {})
    assert response["Status"] == "FAILED", response["Reason"]

    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_update_name():
    # update parameter name
    name = "/test/3-parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PhysicalResourceId" in response
    physical_resource_id = response["PhysicalResourceId"]

    name_2 = "%s-2" % name
    request = Request("Update", name_2, physical_resource_id)
    request["ResourceProperties"]["ReturnSecret"] = True
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PhysicalResourceId" in response
    assert "Data" in response and "Secret" in response["Data"]
    assert "ParameterName" in response["Data"]
    assert name_2 == response["Data"]["ParameterName"]

    physical_resource_id_2 = response["PhysicalResourceId"]
    assert physical_resource_id != physical_resource_id_2

    # delete the parameters
    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    request = Request("Delete", name, physical_resource_id_2)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_update_secret():
    name = "k%s" % uuid.uuid4()
    request = Request("Create", name)
    request["ResourceProperties"]["ReturnSecret"] = True
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PhysicalResourceId" in response
    physical_resource_id = response["PhysicalResourceId"]
    secret_1 = response["Data"]["Secret"]
    secure_hash = response["Data"]["Hash"]
    assert secure_hash == hashlib.md5(secret_1.encode("utf8")).hexdigest()
    assert len(b64decode(response["Data"]["Secret"])) == default_length

    name_2 = "k2%s" % name
    request = Request("Update", name_2, physical_resource_id)
    request["ResourceProperties"]["RefreshOnUpdate"] = True
    request["ResourceProperties"]["ReturnSecret"] = True
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    secure_hash_2 = response["Data"]["Hash"]

    physical_resource_id_2 = response["PhysicalResourceId"]
    assert physical_resource_id != physical_resource_id_2

    secret_2 = response["Data"]["Secret"]
    assert secret_1 != secret_2

    assert secure_hash != secure_hash_2

    # delete secrets
    request = Request("Delete", name, physical_resource_id)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    request = Request("Delete", name, physical_resource_id_2)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_request_duplicate_through_update():
    # update parameter name
    name = "/test/4-parameter-%s" % uuid.uuid4()
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
    name = "/test/5-parameter-%s" % uuid.uuid4()
    request = Request("Create", name)
    request["ResourceProperties"]["ReturnSecret"] = False
    request["ResourceProperties"]["NoEcho"] = False
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "PhysicalResourceId" in response
    physical_resource_id = response["PhysicalResourceId"]

    assert "Data" in response
    assert "Secret" not in response["Data"]
    assert "Arn" in response["Data"]
    assert "NoEcho" in response and response["NoEcho"] == False
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
    assert "NoEcho" in response
    assert response["NoEcho"] == True
    physical_resource_id = response["PhysicalResourceId"]

    # update NoEcho
    request["PhysicalResourceId"] = physical_resource_id
    request["ResourceProperties"]["NoEcho"] = False
    request["RequestType"] = "Update"
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert "NoEcho" in response
    assert response["NoEcho"] == False

    # delete NoEcho parameter
    request["RequestType"] = "Delete"
    request = Request("Delete", name, physical_resource_id)
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
    def __init__(self, request_type, name, physical_resource_id=None):
        self.update(
            {
                "RequestType": request_type,
                "ResponseURL": "https://httpbin.org/put",
                "StackId": "arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid",
                "RequestId": "request-%s" % uuid.uuid4(),
                "ResourceType": "Custom::RandomBytes",
                "LogicalResourceId": "MySecret",
                "ResourceProperties": {"Name": name},
            }
        )
        self["PhysicalResourceId"] = (
            physical_resource_id
            if physical_resource_id is not None
            else str(uuid.uuid4())
        )
