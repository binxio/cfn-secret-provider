import hashlib
import uuid

import boto3

from secrets import handler
from ssm_parameter_name import arn_regexp

ssm_west_1 = boto3.client("ssm", region_name="eu-west-1")
ssm_central_1 = boto3.client("ssm", region_name="eu-central-1")


def correct_response(request, response):
    assert response["Status"] == "SUCCESS", response["Reason"]

    physical_resource_id = response["PhysicalResourceId"]
    region = request["ResourceProperties"].get("Region")

    is_arn = arn_regexp.fullmatch(physical_resource_id)
    assert is_arn
    assert is_arn.group("name") == request["ResourceProperties"]["Name"].strip("/")
    assert not region or is_arn.group("region") == region

    assert "Data" in response
    assert "Secret" in response["Data"]
    assert "Arn" in response["Data"]
    assert "Hash" in response["Data"]
    assert "Version" in response["Data"]
    assert "NoEcho" in response
    assert "ParameterName" in response["Data"]
    assert response["Data"]["Arn"].endswith(response["Data"]["ParameterName"])
    assert response["Data"]["Arn"] == physical_resource_id
    assert (
        response["Data"]["Hash"]
        == hashlib.md5(response["Data"]["Secret"].encode("utf8")).hexdigest()
    )
    assert response["Data"]["Version"] > 0
    assert response["NoEcho"] == True
    return True


def test_create():
    global ssm_west_1, ssm_central_1

    value_central = str(uuid.uuid4())
    name = f"/test/1-parameter-{value_central}"

    value_west = f"west-1 => {value_central}"
    try:
        ssm_west_1.put_parameter(Name=name, Value=value_west, Type="SecureString")
        ssm_central_1.put_parameter(Name=name, Value=value_central, Type="SecureString")

        request = Request("Create", Name=name, Region="eu-west-1")
        response = handler(request, {})
        assert correct_response(request, response)
        response["Data"]["Secret"] == value_west

        new_value = value_west + " updated"

        ssm_west_1.put_parameter(
            Name=name, Value=new_value, Type="SecureString", Overwrite=True
        )
        request = Request(
            "Update",
            physical_resource_id=response["PhysicalResourceId"],
            Name=name,
            Region="eu-west-1",
        )
        response = handler(request, {})
        assert correct_response(request, response)
        assert response["Data"]["Secret"] == new_value
        assert response["Data"]["Version"] == 2

        request = Request(
            "Update",
            physical_resource_id=response["PhysicalResourceId"],
            Name=name,
            Region="eu-central-1",
        )
        response = handler(request, {})
        assert correct_response(request, response)
        assert response["Data"]["Secret"] == value_central

        request = Request(
            "Delete",
            physical_resource_id=response["PhysicalResourceId"],
            Name=name,
            Region="eu-central-1",
        )
        response = handler(request, {})
        response["Status"] == "SUCCESS", response["Reason"]

        request = Request(
            "Delete",
            physical_resource_id=response["PhysicalResourceId"],
            Name=name,
            Region="eu-west-1",
        )
        response = handler(request, {})
        response["Status"] == "SUCCESS", response["Reason"]

    finally:
        ssm_west_1.delete_parameter(Name=name)
        ssm_central_1.delete_parameter(Name=name)


class Request(dict):
    def __init__(self, request_type, physical_resource_id=None, **kwargs):
        self.update(
            {
                "RequestType": request_type,
                "ResponseURL": "https://httpbin.org/put",
                "StackId": "arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid",
                "RequestId": "request-%s" % uuid.uuid4(),
                "ResourceType": "Custom::ReadOnlySecret",
                "LogicalResourceId": "MySecret",
                "ResourceProperties": kwargs,
            }
        )
        self["PhysicalResourceId"] = (
            physical_resource_id
            if physical_resource_id is not None
            else str(uuid.uuid4())
        )
